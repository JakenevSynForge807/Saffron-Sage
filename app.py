from flask import Flask, render_template, request, redirect, url_for, session, make_response
from functools import wraps
from db import db, ensure_order_timestamps
from routes.auth import auth
from routes.main import main
from routes.buyer import buyer
from routes.seller import seller
from decorators import login_required
from controllers.order_controller import get_orders

app = Flask(__name__)
app.secret_key = 'bananas'
app.extensions["db_factory"] = lambda: db()
app.register_blueprint(auth)
app.register_blueprint(main)
app.register_blueprint(buyer)
app.register_blueprint(seller)

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
    return response

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
    app.run(debug=True)