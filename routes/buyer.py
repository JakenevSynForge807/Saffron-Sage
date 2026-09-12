from flask import Blueprint
import controllers.buyer_controller as ctrl
from decorators import login_required, buyer_only
buyer = Blueprint('buyer', __name__)

@buyer.route("/cart/add/<int:dishid>", methods=["POST"])
@login_required
@buyer_only
def add_to_cart(dishid):
    return ctrl.add_to_cart(dishid)

@buyer.route("/order/cancel/<int:id>", methods=["POST"])
@login_required
@buyer_only
def cancel_order(id):
    return ctrl.cancel_order(id)
    
@buyer.route("/myorders")
@login_required
@buyer_only
def my_orders():
    return ctrl.my_orders()
    
@buyer.route("/yourcart")  
@login_required
@buyer_only  
def your_cart(): 
    return ctrl.your_cart()
    
@buyer.route("/cart/remove/<int:id>", methods=["POST"])
@login_required
@buyer_only
def remove_cart_dish(id):
    return ctrl.remove_cart_dish(id)
    
@buyer.route("/cart/update/<int:cartid>", methods=["POST"])
@login_required
@buyer_only
def update_cart(cartid):
    return ctrl.update_cart(cartid)

@buyer.route("/checkout", methods=["GET", "POST"])   
@login_required 
@buyer_only
def checkout():
    return ctrl.checkout()