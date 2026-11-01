from functools import wraps
from flask import redirect, session, url_for, jsonify, request

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "id" not in session:
            if "application/json" in request.headers.get("Accept", ""):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def seller_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "seller":
            return "Sellers only.", 403
        return view(*args, **kwargs)
    return wrapped


def buyer_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "buyer":
            return "Buyers only.", 403
        return view(*args, **kwargs)
    return wrapped
