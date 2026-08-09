from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps

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

def db():
    conn = sqlite3.connect("saffron.db")
    conn.row_factory = sqlite3.Row
    
    return conn

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menu")
def menu(): 
    dishes = {
        "Starters": [
            {"name": "Heritage Tomato Salad", "desc": "Basil, aged balsamic, burrata", "price": "8.50"},
            {"name": "Wild Mushroom Soup", "desc": "Truffle oil, toasted sourdough", "price": "7.00"}
        ],
        
        "Mains": [
            {"name": "Pan-Seared Sea Bass", "desc": "Crushed new potatoes, samphire", "price": "18.00"},
            {"name": "Slow-Braised Short Rib", "desc": "Root mash, red wine jus", "price": "21.50"}
        ],
        
        "Desserts": [
            {"name": "Sticky Toffee Pudding", "desc": "Vanilla bean ice cream", "price": "6.50"}
        ],
    }
    
    return render_template("menu.html", dishes = dishes)

@app.route("/reservations", methods=["GET", "POST"])
def reservations():
    reservationsMessage = None
    
    if request.method=="POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        date = request.form["date"]
        time = request.form["time"]
        guests = request.form["guests"]
        seating = request.form["seating"]   
        occasion = request.form["occasion"]
        special_requests = request.form.get("special_requests", "")     
        
        conn = db()
        conn.execute("""INSERT INTO reservations(first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    Values(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    )    
            
        conn.commit(); conn.close()
        reservationsMessage = f"Thank you {first_name}! Your table is booked for {date} at {time}."     
                   
    return render_template("reservations.html", reservationsMessage=reservationsMessage)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    contactMessage = None
    
    if request.method=="POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]
        
        conn = db()
        conn.execute("""INSERT INTO contact(name, email, message)
                    Values(?, ?, ?)""",
                    (name, email, message)
                    )  
            
        conn.commit(); conn.close()
        contactMessage = f"Thank you {name}! Your message has been sent successfully."
    
    return render_template("contact.html", contactMessage=contactMessage)

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

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
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        user = conn.execute("SELECT * FROM usersInfo WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
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

@app.route("/dashboard")
@login_required
@no_cache
def dashboard():
    if session["role"] == "seller":
        conn = db()
        my_dishes = conn.execute("select * from dishesTable where sellerid = ?", (session["id"],)).fetchall()
        
        return render_template("seller_dashboard.html", my_dishes=my_dishes)

    return render_template("buyer_dashboard.html")

@app.route("/seller/add", methods=["POST"])
@login_required
@seller_only
def add_dish():
    dishname = request.form["dishname"]
    dishprice = request.form["dishprice"]
    
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
    conn=db()
    conn.execute("""DELETE FROM dishesTable WHERE id=? and sellerid=?""",
                 (id, session["id"])                 
                 )
    
    conn.commit(); conn.close()
    flash("Dish removed successfully.", "ok")
    
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)