from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from decimal import Decimal, InvalidOperation
from functools import wraps
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'bananas'

@app.before_request
def check_session():
    protected_routes = ["dashboard", "logout"]
    if request.endpoint in protected_routes and "id" not in session:
        return redirect(url_for("login"))

@app.after_request
def add_response_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def ensure_order_timestamps(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(orderTable)")}
    if not columns:
        return
    if "created_at" not in columns:
        conn.execute("ALTER TABLE orderTable ADD COLUMN created_at TEXT")
    if "order_group_id" not in columns:
        conn.execute("ALTER TABLE orderTable ADD COLUMN order_group_id INTEGER")
    # Existing dates are unknown; only stamp newly inserted orders.
    conn.execute("""CREATE TRIGGER IF NOT EXISTS stamp_order_created_at
        AFTER INSERT ON orderTable WHEN NEW.created_at IS NULL
        BEGIN
            UPDATE orderTable SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END""")
    conn.commit()


def db():
    conn = sqlite3.connect(Path(__file__).with_name("saffron.db"))
    conn.row_factory = sqlite3.Row
    ensure_order_timestamps(conn)
    
    return conn

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menu")
def menu(): 
    conn = db()
    dishes = conn.execute("""SELECT dishesTable.dishname, dishesTable.dishprice,
        usersInfo.fullname AS seller FROM dishesTable
        JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
        ORDER BY usersInfo.fullname, dishesTable.dishname""").fetchall()
    conn.close()
    return render_template("menu.html", dishes=dishes)

@app.route("/reservations", methods=["GET", "POST"])
def reservations():
    reservationsMessage = None
    
    if request.method=="POST":
        first_name = request.form.get("first_name", "")
        last_name = request.form.get("last_name", "")
        email = request.form.get("email", "")
        date = request.form.get("date", "")
        time = request.form.get("time", "")
        guests = request.form.get("guests", "")
        seating = request.form.get("seating", "")   
        occasion = request.form.get("occasion", "none")
        special_requests = request.form.get("special_requests", "")     
        
        try:
            booking_time = datetime.fromisoformat(date + "T" + time)
            valid = (first_name.strip() and last_name.strip() and "@" in email
                     and booking_time > datetime.now() and 1 <= int(guests) <= 12
                     and seating in ("indoor", "outdoor")
                     and occasion in ("none", "birthday", "anniversary")
                     and request.form.get("terms"))
        except ValueError:
            valid = False
        if not valid:
            flash("Please enter valid booking details, a future date and time, and accept the booking terms.", "bad")
            return redirect(url_for("reservations"))

        conn = db()
        conn.execute("""INSERT INTO reservations(first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    Values(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    )    
            
        conn.commit(); conn.close()
        flash(f"Thank you {first_name}! Your table is booked for {date} at {time}.", "ok")
        return redirect(url_for("reservations"))     
                   
    return render_template("reservations.html", reservationsMessage=reservationsMessage)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contactus", methods=["GET", "POST"])
def contact():
    contactMessage = None
    
    if request.method=="POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        message = request.form.get("message", "")
        
        if not name.strip() or "@" not in email or not message.strip() or len(message) > 300:
            flash("Please enter your name, email and a message of up to 300 characters.", "bad")
            return redirect(url_for("contact"))
        conn = db()
        conn.execute("""INSERT INTO contact(name, email, message)
                    Values(?, ?, ?)""",
                    (name, email, message)
                    )  
            
        conn.commit(); conn.close()
        flash(f"Thank you {name}! Your message has been saved successfully.", "ok")
        return redirect(url_for("contact"))
    
    return render_template("contact.html", contactMessage=contactMessage)

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        fullname = request.form.get("fullname", "")
        email = request.form.get("email", "")
        raw_password = request.form.get("password", "")
        role = request.form.get("role", "")
        fullname = fullname.strip()
        email = email.strip()
        if not fullname or "@" not in email or len(raw_password) < 6 or role not in ("buyer", "seller"):
            flash("Enter your name, a valid email, a password of at least 6 characters, and choose buyer or seller.", "bad")
            return redirect(url_for("signup"))
        password = generate_password_hash(raw_password)

        conn = db()

        try:
            conn.execute(
                """
                INSERT INTO usersInfo(fullname, email, password, role)
                VALUES (?, ?, ?, ?)
                """,
                (fullname, email, password, role)
            )

            conn.commit()

            flash(
                f"Thank you {fullname}! Your account has been created successfully.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash(
                f"Error: The email '{email}' is already registered. Please use a different email.",
                "error"
            )

        finally:
            conn.close()

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute("SELECT * FROM usersInfo WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["id"] = user["id"]
            session["fullname"] = user["fullname"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    session.modified=True
    response=make_response(redirect(url_for("login")))
    response.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if "id" not in session:
            return redirect(url_for("login"))
        return view(*a, **k)
    return wrapped

def no_cache(view):
    @wraps(view)
    def wrapped(*a, **k):
        response = make_response(view(*a, **k))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return wrapped

def seller_only(view):
    @wraps(view)
    def wrapped(*a, **k):
        if session.get("role") != "seller":
            return "Sellers only.", 403
        return view(*a, **k)
    return wrapped

def buyer_only(view):
    @wraps(view)
    def wrapped(*a, **k):
        if session.get("role") != "buyer":
            return "Buyers only.", 403
        return view(*a, **k)
    return wrapped

def get_orders(conn, user_id, role):
    # Each row remains a dish item; items from one checkout/seller share an order number.
    owner_column = "dishesTable.sellerid" if role == "seller" else "orderTable.buyerid"
    rows = conn.execute(f"""SELECT orderTable.*, dishesTable.dishname AS dish,
        dishesTable.dishprice, dishesTable.sellerid,
        buyer.fullname AS buyer, seller.fullname AS seller,
        orderTable.fullname AS recipient
        FROM orderTable JOIN dishesTable ON orderTable.dishid = dishesTable.id
        JOIN usersInfo AS buyer ON orderTable.buyerid = buyer.id
        JOIN usersInfo AS seller ON dishesTable.sellerid = seller.id
        WHERE {owner_column} = ? ORDER BY orderTable.id DESC""", (user_id,)).fetchall()
    orders = {}
    for row in rows:
        order_id = row["order_group_id"] or row["id"]
        if order_id not in orders:
            orders[order_id] = dict(row)
            orders[order_id].update(id=order_id, items=[], quantity=0, total=0)
        order = orders[order_id]
        order["items"].append({"dish": row["dish"], "quantity": row["quantity"]})
        order["quantity"] += row["quantity"]
        order["total"] += row["dishprice"] * row["quantity"]
    return sorted(orders.values(), key=lambda order: order["id"], reverse=True)


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

@app.route("/seller/history")
@login_required
@seller_only
def seller_history():
    conn = db()
    orders = get_orders(conn, session["id"], "seller")
    conn.close()
    return render_template("seller_history.html", my_orders=orders)


@app.route("/cart/add/<int:dishid>", methods=["POST"])
@login_required
@buyer_only
def add_to_cart(dishid):
    try:
        quantity = int(request.form.get("quantity", 1))
        if not 1 <= quantity <= 20:
            raise ValueError
    except ValueError:
        flash("Choose a whole-number quantity from 1 to 20.", "bad")
        return redirect(url_for("your_cart"))
    
    conn = db()
    if not conn.execute("SELECT id FROM dishesTable WHERE id = ?", (dishid,)).fetchone():
        conn.close()
        flash("That dish is no longer available.", "bad")
        return redirect(url_for("dashboard"))
    existing = conn.execute("Select * from cartItems where buyerid = ? and dishid = ?", (session["id"], dishid)).fetchone()
    
    if existing and existing["quantity"] + quantity > 20:
        conn.close()
        flash("You can add at most 20 of each dish.", "bad")
        return redirect(url_for("your_cart"))
    if existing:
        conn.execute("Update cartItems set quantity = quantity + ? where buyerid = ? and dishid = ?", (quantity, session["id"], dishid))
    else:
        conn.execute(
                        """
                        INSERT INTO cartItems(dishid, buyerid, quantity)
                        VALUES (?, ?, ?)
                        """,
                        (dishid, session["id"], quantity)
                    )

    conn.commit(); conn.close()
    flash("Added to cart successfully.", "ok")
    
    return redirect(url_for("dashboard"))

@app.route("/seller/add", methods=["POST"])
@login_required
@seller_only
def add_dish():
    dishname = request.form.get("dishname", "").strip()
    try:
        price = Decimal(request.form.get("dishprice", ""))
        if not dishname or not price.is_finite() or price <= 0 or price > Decimal("999999.99") or price != price.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, ValueError):
        flash("Enter a dish name and a positive price with at most two decimal places (maximum 999,999.99).", "bad")
        return redirect(url_for("dashboard"))
    dishprice = float(price)
    
    conn = db()
    conn.execute("""INSERT INTO dishesTable(dishname, dishprice, sellerid)
                 Values(?, ?, ?)""",  
                 (dishname, dishprice, session["id"])
                )  
    
    conn.commit(); conn.close()
    flash("Dish added successfully.", "ok")
    
    return redirect(url_for("dashboard"))

@app.route("/seller/delete/<int:id>", methods=["POST"])
@login_required
@seller_only
def delete_dish(id):
    conn = db()
    # Preserve dishes referenced by orders, keeping history and sales intact.
    result = conn.execute("""DELETE FROM dishesTable WHERE id = ? AND sellerid = ?
        AND NOT EXISTS (SELECT 1 FROM orderTable WHERE dishid = dishesTable.id)""",
        (id, session["id"]))
    if result.rowcount:
        conn.execute("DELETE FROM cartItems WHERE dishid = ?", (id,))
        flash("Dish removed successfully.", "ok")
    else:
        flash("This dish could not be deleted. Dishes with orders must be kept to preserve order history.", "bad")
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/order/cancel/<int:id>", methods=["POST"])
@login_required
@buyer_only
def cancel_order(id):
    conn = db()
    result = conn.execute("""UPDATE orderTable SET status = 'cancelled' WHERE COALESCE(order_group_id, id) = ? and buyerid = ? and status = 'pending'""",
                 (id, session["id"])                 
                 )
    
    conn.commit(); conn.close()
    flash("Order cancelled." if result.rowcount else "This order can no longer be cancelled.", "ok" if result.rowcount else "bad")
    
    return redirect(url_for("my_orders"))

@app.route("/myorders")
@login_required
@buyer_only
def my_orders():
    conn = db()

    orders = get_orders(conn, session["id"], "buyer")
    conn.close()
    total = sum(order["total"] for order in orders if order["status"] != "cancelled")

    return render_template("myorders.html", orders=orders, total=total)

@app.route("/yourcart")  
@login_required
@buyer_only  
def your_cart():    
    conn = db()
    items = conn.execute("""SELECT cartItems.id, cartItems.quantity, dishesTable.id AS dish_id, 
                         dishesTable.dishname, dishesTable.dishprice, usersInfo.fullname AS seller FROM 
                         cartItems JOIN dishesTable ON cartItems.dishid = dishesTable.id JOIN
                         usersInfo ON dishesTable.sellerid = usersInfo.id WHERE cartItems.buyerid
                         = ?""", (session["id"],)).fetchall()
    
    conn.commit(); conn.close()
    
    subtotal = sum(i["dishprice"] * i["quantity"] for i in items)
    deliveryFee = 2.50 if subtotal > 0 else 0
    total = subtotal + deliveryFee
    
    return render_template("yourcart.html", items=items, subtotal=subtotal, deliveryFee=deliveryFee, total=total)

@app.route("/cart/remove/<int:id>", methods=["POST"])
@login_required
@buyer_only
def remove_cart_dish(id):
    conn = db()
    conn.execute("""DELETE FROM cartItems WHERE id=? AND buyerid=?""",
                 (id, session["id"])                 
                 )
    
    conn.commit(); conn.close()
    flash("This dish has been removed from your cart.", "ok")
    
    return redirect(url_for("your_cart"))

@app.route("/cart/update/<int:cartid>", methods=["POST"])
@login_required
@buyer_only
def update_cart(cartid):
    try:
        quantity = int(request.form.get("quantity", 1))
        if not 1 <= quantity <= 20:
            raise ValueError
    except ValueError:
        flash("Choose a whole-number quantity from 1 to 20.", "bad")
        return redirect(url_for("your_cart"))
    
    conn = db()
        
    conn.execute(
                    """
                    UPDATE cartItems SET quantity = ? WHERE id = ? AND buyerid = ?
                    """,
                    (quantity, cartid, session["id"])
                )

    conn.commit(); conn.close()
    flash("Cart updated successfully.", "ok")
    
    return redirect(url_for("your_cart"))

@app.route("/checkout", methods=["GET", "POST"])   
@login_required 
@buyer_only
def checkout():
    conn = db()
    
    items = conn.execute("""SELECT cartItems.quantity, dishesTable.id AS dishid, dishesTable.sellerid, 
                        dishesTable.dishname, dishesTable.dishprice, usersInfo.fullname AS 
                        seller FROM cartItems JOIN dishesTable ON cartItems.dishid = 
                        dishesTable.id JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
                        WHERE cartItems.buyerid = ?""", 
                        (session["id"],)).fetchall()
    
    if not items:
        conn.close()
        flash("Your cart is empty.", "bad")
        return redirect(url_for("your_cart"))
    
    subtotal = sum(i["dishprice"] * i["quantity"] for i in items)
    deliveryFee = 2.50 if subtotal > 0 else 0
    total = subtotal + deliveryFee
    
    if request.method == "POST":
        fullname = str(request.form.get("fullname", "")).strip()
        phone = str(request.form.get("phone", "")).strip()
        deliveryAddress = str(request.form.get("deliveryAddress", "")).strip()
        notes = str(request.form.get("notes", "")).strip()
        paymentMethod = str(request.form.get("paymentMethod", "")).strip()

        if not fullname or not phone or not deliveryAddress or paymentMethod not in ("cash", "card"):
            conn.close()
            flash("Enter your delivery details and select a payment method.", "bad")
            return redirect(url_for("checkout"))
        if any(not 1 <= item["quantity"] <= 20 for item in items):
            conn.close()
            flash("Please correct the quantities in your cart before checking out.", "bad")
            return redirect(url_for("your_cart"))

        buyerid = int(session["id"])
        seller_orders = {}
        created_at = conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]

        for item in items:
            dishid = int(item["dishid"])
            quantity = int(item["quantity"])

            result = conn.execute(
                """INSERT INTO orderTable(dishid, buyerid, quantity, fullname, phone, deliveryAddress,
                   notes, paymentMethod, created_at, order_group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (dishid, buyerid, quantity, fullname, phone, deliveryAddress, notes, paymentMethod,
                 created_at, seller_orders.get(item["sellerid"]))
            )
            if item["sellerid"] not in seller_orders:
                seller_orders[item["sellerid"]] = result.lastrowid
                conn.execute("UPDATE orderTable SET order_group_id = ? WHERE id = ?",
                             (result.lastrowid, result.lastrowid))
    
        conn.execute(
            """DELETE FROM cartItems WHERE buyerid = ?""",
            (buyerid,)
        )
    
        conn.commit(); conn.close()
        
        flash("Order placed! It is now visible on the seller dashboard.", "ok")
        
        return redirect(url_for("my_orders"))
    
    conn.commit(); conn.close()
    
    return render_template("checkout.html", items=items, subtotal=subtotal, deliveryFee=deliveryFee, total=total)

def update_seller_order(id, previous_status, new_status, message):
    conn = db()
    result = conn.execute("""UPDATE orderTable SET status = ?
        WHERE COALESCE(order_group_id, id) = ? AND status = ?
        AND dishid IN (SELECT id FROM dishesTable WHERE sellerid = ?)""",
        (new_status, id, previous_status, session["id"]))
    changed = result.rowcount
    conn.commit()
    conn.close()
    flash(message if changed else "Order could not be updated. It may have changed already or is unavailable.",
          "ok" if changed else "bad")
    return redirect(url_for("dashboard"))


@app.route("/seller/accept/<int:id>", methods=["POST"])
@login_required
@seller_only
def accept_order(id):
    return update_seller_order(id, "pending", "accepted", "Order accepted.")


@app.route("/seller/cancel/<int:id>", methods=["POST"])
@login_required
@seller_only
def cancel_order_seller(id):
    return update_seller_order(id, "pending", "cancelled", "Order cancelled.")


@app.route("/complete/<int:id>", methods=["POST"])
@login_required
@seller_only
def complete_order(id):
    return update_seller_order(id, "accepted", "completed", "Order marked as completed.")

if __name__ == "__main__":
    app.run(debug=True)