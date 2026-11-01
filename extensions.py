from flask import request, session
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect

def rate_limit_key():
    return f"user:{session['id']}" if 'id' in session else f"ip:{request.remote_addr}"

csrf = CSRFProtect()
limiter = Limiter(key_func=rate_limit_key, storage_uri="memory://", default_limits=["100 per hour"])