import logging
import os
import secrets
import time
from functools import wraps
from threading import Lock, Thread

from flask import Flask, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_limiter.errors import RateLimitExceeded
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from controllers.order_controller import get_orders
from db import db, ensure_order_timestamps
from decorators import login_required
from extensions import csrf, limiter
from routes.auth import auth
from routes.buyer import buyer
from routes.main import main
from routes.seller import seller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)

if config.SECRET_KEY:
    app.secret_key = config.SECRET_KEY
elif config.ON_RENDER:
    raise RuntimeError("SECRET_KEY must be set on Render (Environment > Add Environment Variable).")
else:
    # Local development only: sessions reset when the server restarts.
    app.secret_key = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY is not set; using a temporary development key.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.ON_RENDER,  # Render serves HTTPS
    WTF_CSRF_TIME_LIMIT=None,  # token lives as long as the session
)
# Render sits behind a proxy: trust its X-Forwarded-* headers for the real
# client IP (rate limiting) and https scheme (secure cookies, redirects).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

app.extensions["db_factory"] = lambda: db()
csrf.init_app(app)
limiter.init_app(app)

if not config.GEMINI_API_KEY:
    app.logger.error("GEMINI_API_KEY is not set: the AI assistant will be unavailable.")

app.register_blueprint(auth)
app.register_blueprint(main)
app.register_blueprint(buyer)
app.register_blueprint(seller)

vector_store_sync_lock = Lock()
SYNC_RETRY_SECONDS = 300


def sync_vector_store():
    try:
        from knowledge_base import sync_all
        sync_all()
    except Exception:
        app.logger.exception("Vector-store synchronization failed; it will be retried later.")
        app.config["VECTOR_STORE_SYNC_FAILED_AT"] = time.monotonic()
        app.config["VECTOR_STORE_SYNC_STARTED"] = False
    else:
        app.config["VECTOR_STORE_INITIALIZED"] = True


@app.before_request
def initialize_vector_store():
    if request.method == "HEAD" or app.testing:
        return

    if app.config.get("VECTOR_STORE_INITIALIZED") or app.config.get("VECTOR_STORE_SYNC_STARTED"):
        return

    failed_at = app.config.get("VECTOR_STORE_SYNC_FAILED_AT")
    if failed_at and time.monotonic() - failed_at < SYNC_RETRY_SECONDS:
        return

    with vector_store_sync_lock:
        if app.config.get("VECTOR_STORE_INITIALIZED") or app.config.get("VECTOR_STORE_SYNC_STARTED"):
            return

        sync_thread = Thread(target=sync_vector_store, name="vector-store-sync", daemon=True)
        sync_thread.start()
        app.config["VECTOR_STORE_SYNC_STARTED"] = True


@app.before_request
def check_session():
    protected_routes = ["dashboard", "logout"]
    if request.endpoint in protected_routes and "id" not in session:
        return redirect(url_for("auth.login"))


@app.after_request
def add_response_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def _wants_json():
    return "application/json" in request.headers.get("Accept", "")


def _back():
    return redirect(request.referrer or url_for("main.home"))


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    message = "Your form expired. Please refresh the page and try again."
    if _wants_json():
        return jsonify(error=message), 400
    flash(message, "bad")
    return _back()


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit(error):
    message = "You're sending messages too quickly. Please wait a minute and try again."
    if _wants_json():
        return jsonify(error=message), 429
    flash(message, "bad")
    return _back()


def no_cache(view):
    @wraps(view)
    def wrapped(*a, **k):
        response = make_response(view(*a, **k))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return wrapped


@app.route("/dashboard")
@login_required
@no_cache
def dashboard():
    if session["role"] == "seller":
        conn = db()
        my_dishes = conn.execute("select * from dishesTable where sellerid = ?", (session["id"],)).fetchall()
        my_orders = get_orders(conn, session["id"], "seller")
        completedSales = sum(order["total"] for order in my_orders if order["status"] == "completed")
        pendingCount = sum(1 for order in my_orders if order["status"] == 'pending')
        completedCount = sum(1 for order in my_orders if order["status"] == 'completed')
        acceptedCount = sum(1 for order in my_orders if order["status"] == 'accepted')
        cancelledCount = sum(1 for order in my_orders if order["status"] == 'cancelled')

        conn.commit(); conn.close()

        return render_template("seller_dashboard.html", my_dishes=my_dishes, totalDishes=len(my_dishes), my_orders=[order for order in my_orders if order["status"] in ("pending", "accepted")], pendingCount=pendingCount, completedCount=completedCount, acceptedCount=acceptedCount, cancelledCount=cancelledCount, completedSales=completedSales)

    conn = db()
    seller_dishes = conn.execute("select dishesTable.id, dishesTable.dishname, dishesTable.dishprice, usersInfo.fullname as seller from dishesTable join usersInfo on dishesTable.sellerid = usersInfo.id").fetchall()

    conn.close()

    return render_template("buyer_dashboard.html", seller_dishes=seller_dishes)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")