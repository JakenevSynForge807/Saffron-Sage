from flask import Blueprint
import controllers.seller_controller as ctrl
from decorators import login_required, seller_only
seller = Blueprint('seller', __name__)

@seller.route("/seller/history")
@login_required
@seller_only
def seller_history():
    return ctrl.seller_history()

@seller.route("/seller/add", methods=["POST"])
@login_required
@seller_only
def add_dish():
    return ctrl.add_dish()

@seller.route("/seller/delete/<int:id>", methods=["POST"])
@login_required
@seller_only
def delete_dish(id):
    return ctrl.delete_dish(id)

def update_seller_order(id, previous_status, new_status, message):
    return ctrl.update_seller_order(id, previous_status, new_status, message)

@seller.route("/seller/accept/<int:id>", methods=["POST"])
@login_required
@seller_only
def accept_order(id):
    return update_seller_order(id, "pending", "accepted", "Order accepted.")

@seller.route("/seller/cancel/<int:id>", methods=["POST"])
@login_required
@seller_only
def cancel_order_seller(id):
    return update_seller_order(id, "pending", "cancelled", "Order cancelled.")

@seller.route("/complete/<int:id>", methods=["POST"])
@login_required
@seller_only
def complete_order(id):
    return update_seller_order(id, "accepted", "completed", "Order marked as completed.")

