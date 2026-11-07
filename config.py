import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "saffron.db"))
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", DATA_DIR / "chroma_db"))
ON_RENDER = bool(os.environ.get("ON_RENDER"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
EMBEDDING_MODEL = os.environ.get("GEMINI_MODEL", "gemini-embedding-001")
GEMINI_TIMEOUT_SECONDS = max(10, int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "25")))
RAG_MAX_DISTANCE = float(os.environ.get("RAG_MAX_DISTANCE", "0.40"))
CHAT_HISTORY_MESSAGES = int(os.environ.get("CHAT_HISTORY_MESSAGES", "10"))
ASSISTANT_RATE_LIMIT = os.environment.get("ASSISTANT_RATE_LIMIT", "10 per minute:100 per day")
SECRET_KEY = os.environ.get("SECRET_KEY")
 

