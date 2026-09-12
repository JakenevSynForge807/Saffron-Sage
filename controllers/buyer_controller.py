from flask import current_app, render_template, request, redirect, url_for, flash, session
from controllers.order_controller import get_orders

def get_db():
    return current_app.extensions["db_factory"]()

def add_to_cart(dishid):
    try:
        quantity = int(request.form.get("quantity", 1))
        if not 1 <= quantity <= 20:
            raise ValueError
    except ValueError:
        flash("Choose a whole-number quantity from 1 to 20.", "bad")
        return redirect(url_for("buyer.your_cart"))
    
    conn = get_db()
    if not conn.execute("SELECT id FROM dishesTable WHERE id = ?", (dishid,)).fetchone():
        conn.close()
        flash("That dish is no longer available.", "bad")
        return redirect(url_for("dashboard"))
    existing = conn.execute("Select * from cartItems where buyerid = ? and dishid = ?", (session["id"], dishid)).fetchone()
    
    if existing and existing["quantity"] + quantity > 20:
        conn.close()
        flash("You can add at most 20 of each dish.", "bad")
        return redirect(url_for("buyer.your_cart"))
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

def cancel_order(id):
    conn = get_db()
    result = conn.execute("""UPDATE orderTable SET status = 'cancelled' WHERE COALESCE(order_group_id, id) = ? and buyerid = ? and status = 'pending'""",
                 (id, session["id"])                 
                 )
    
    conn.commit(); conn.close()
    flash("Order cancelled." if result.rowcount else "This order can no longer be cancelled.", "ok" if result.rowcount else "bad")
    
    return redirect(url_for("buyer.my_orders"))

def my_orders():
    conn = get_db()

    orders = get_orders(conn, session["id"], "buyer")
    conn.close()
    total = sum(order["total"] for order in orders if order["status"] != "cancelled")

    return render_template("myorders.html", orders=orders, total=total)

def your_cart():    
    conn = get_db()
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

def remove_cart_dish(id):
    conn = get_db()
    conn.execute("""DELETE FROM cartItems WHERE id=? AND buyerid=?""",
                 (id, session["id"])                 
                 )
    
    conn.commit(); conn.close()
    flash("This dish has been removed from your cart.", "ok")
    
    return redirect(url_for("buyer.your_cart"))

def update_cart(cartid):
    try:
        quantity = int(request.form.get("quantity", 1))
        if not 1 <= quantity <= 20:
            raise ValueError
    except ValueError:
        flash("Choose a whole-number quantity from 1 to 20.", "bad")
        return redirect(url_for("buyer.your_cart"))
    
    conn = get_db()
        
    conn.execute(
                    """
                    UPDATE cartItems SET quantity = ? WHERE id = ? AND buyerid = ?
                    """,
                    (quantity, cartid, session["id"])
                )

    conn.commit(); conn.close()
    flash("Cart updated successfully.", "ok")
    
    return redirect(url_for("buyer.your_cart"))

def checkout():
    conn = get_db()
    
    items = conn.execute("""SELECT cartItems.quantity, dishesTable.id AS dishid, dishesTable.sellerid, 
                        dishesTable.dishname, dishesTable.dishprice, usersInfo.fullname AS 
                        seller FROM cartItems JOIN dishesTable ON cartItems.dishid = 
                        dishesTable.id JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
                        WHERE cartItems.buyerid = ?""", 
                        (session["id"],)).fetchall()
    
    if not items:
        conn.close()
        flash("Your cart is empty.", "bad")
        return redirect(url_for("buyer.your_cart"))
    
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
            return redirect(url_for("buyer.checkout"))
        if any(not 1 <= item["quantity"] <= 20 for item in items):
            conn.close()
            flash("Please correct the quantities in your cart before checking out.", "bad")
            return redirect(url_for("buyer.your_cart"))

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
        
        return redirect(url_for("buyer.my_orders"))
    
    conn.commit(); conn.close()
    
    return render_template("checkout.html", items=items, subtotal=subtotal, deliveryFee=deliveryFee, total=total)
