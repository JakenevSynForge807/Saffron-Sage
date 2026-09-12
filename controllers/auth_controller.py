from flask import current_app, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

def get_db():
    return current_app.extensions["db_factory"]()

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
            return redirect(url_for("auth.signup"))
        password = generate_password_hash(raw_password)

        conn = get_db()

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

            return redirect(url_for("auth.login"))

        except sqlite3.IntegrityError:
            flash(
                f"Error: The email '{email}' is already registered. Please use a different email.",
                "error"
            )

        finally:
            conn.close()

    return render_template("signup.html")

def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        conn = get_db()
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

def logout():
    session.clear()
    session.modified=True
    response=make_response(redirect(url_for("auth.login")))
    response.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response