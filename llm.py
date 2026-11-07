import logging
from threading import Lock
import httpx
from google import genai
from google.genai import types, errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import config

log = logging.getLogger(__name__)
_client = None
_client_lock = Lock()

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
EMBED_BATCH_SIZE = 50

class AssistantError(Exception):
    pass
class AssistantNotConfiguredError(AssistantError):
    pass
class AssistantBusy(AssistantError):
    pass
class AssistantTimeout(AssistantError):
    pass

def get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not config.GEMINI_API_KEY:
                    raise AssistantNotConfiguredError("GEMINI_API_KEY is not set.")
                _client = genai.Client(
                    api_key=config.GEMINI_API_KEY,
                    http_options=types.HttpOptions(timeout=config.GEMINI_TIMEOUT_SECONDS * 1000),
                )
    return _client

def _is_retryable(exc):
    return isinstance(exc, errors.APIError) and exc.code in RETRYABLE_STATUS

def generate(contents, system_instruction):
    client = get_client()
    models = [config.GEMINI_MODEL]
    if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
        models.append(config.GEMINI_FALLBACK_MODEL)

    last_error = None
    for model in models:
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
                    max_output_tokens=600,
                ),
            )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AssistantTimeout("Gemini timed out.") from exc
        except errors.APIError as exc:
            last_error = exc
            if exc.code == 404 or _is_retryable(exc):
                log.warning("Gemini model %s failed with HTTP %s.", model, exc.code)
                continue
            raise
    if last_error is not None and last_error.code == 404:
        raise last_error
    raise AssistantBusy("All Gemini models are busy.") from last_error


@retry(retry=retry_if_exception(_is_retryable),
       wait=wait_exponential(multiplier=2, min=2, max=30),
       stop=stop_after_attempt(5), reraise=True)
def _embed_batch(texts, task_type):
    response = get_client().models.embed_content(
        model=config.EMBEDDING_MODEL, contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [e.values for e in response.embeddings]

def embed_documents(texts):
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        vectors.extend(_embed_batch(texts[start:start + EMBED_BATCH_SIZE], "RETRIEVAL_DOCUMENT"))
    return vectors


def embed_query(text):
    response = get_client().models.embed_content(
        model=config.EMBEDDING_MODEL, contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return response.embeddings[0].values