from flask import current_app, render_template, request, redirect, url_for, flash, session
from decimal import Decimal, InvalidOperation
from controllers.order_controller import get_orders

def get_db():
    return current_app.extensions["db_factory"]()

def seller_history():
    conn = get_db()
    orders = get_orders(conn, session["id"], "seller")
    conn.close()
    return render_template("seller_history.html", my_orders=orders)

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
    
    conn = get_db()
    conn.execute("""INSERT INTO dishesTable(dishname, dishprice, sellerid)
                 Values(?, ?, ?)""",  
                 (dishname, dishprice, session["id"])
                )  
    
    conn.commit(); conn.close()
    flash("Dish added successfully.", "ok")
    
    return redirect(url_for("dashboard"))

def delete_dish(id):
    conn = get_db()
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

def update_seller_order(id, previous_status, new_status, message):
    conn = get_db()
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

def accept_order(id):
    return update_seller_order(id, "pending", "accepted", "Order accepted.")

def cancel_order_seller(id):
    return update_seller_order(id, "pending", "cancelled", "Order cancelled.")

def complete_order(id):
    return update_seller_order(id, "accepted", "completed", "Order marked as completed.")