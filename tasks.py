import logging
from concurrent.futures import ThreadPoolExecutor
log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="background")

def _run(func, args):
    try:
        func(*args)
    except Exception:
        log.exception("background job %s%r failed", func.__name__, args)
        
def run_in_background(func, *args):
    return _executor.submit(_run, func, args)