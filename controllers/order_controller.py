def get_orders(conn, user_id, role):
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
