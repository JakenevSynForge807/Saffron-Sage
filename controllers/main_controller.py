from flask import current_app, render_template, request, redirect, url_for, flash, session
from datetime import datetime

def get_db():
    return current_app.extensions["db_factory"]()

def home():
    return render_template("index.html")

def menu(): 
    conn = get_db()
    dishes = conn.execute("""SELECT dishesTable.dishname, dishesTable.dishprice,
        usersInfo.fullname AS seller FROM dishesTable
        JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
        ORDER BY usersInfo.fullname, dishesTable.dishname""").fetchall()
    conn.close()
    return render_template("menu.html", dishes=dishes)

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
            return redirect(url_for("main.reservations"))

        conn = get_db()
        conn.execute("""INSERT INTO reservations(first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    Values(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (first_name, last_name, email, date, time, guests, seating, occasion, special_requests)
                    )    
            
        conn.commit(); conn.close()
        flash(f"Thank you {first_name}! Your table is booked for {date} at {time}.", "ok")
        return redirect(url_for("main.reservations"))
                   
    return render_template("reservations.html", reservationsMessage=reservationsMessage)

def about():
    return render_template("about.html")

def contact():
    contactMessage = None
    
    if request.method=="POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        message = request.form.get("message", "")
        
        if not name.strip() or "@" not in email or not message.strip() or len(message) > 300:
            flash("Please enter your name, email and a message of up to 300 characters.", "bad")
            return redirect(url_for("main.contact"))
        conn = get_db()
        conn.execute("""INSERT INTO contact(name, email, message)
                    Values(?, ?, ?)""",
                    (name, email, message)
                    )  
            
        conn.commit(); conn.close()
        flash(f"Thank you {name}! Your message has been saved successfully.", "ok")
        return redirect(url_for("main.contact"))
    
    return render_template("contact.html", contactMessage=contactMessage)

