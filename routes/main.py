from flask import Blueprint
import controllers.main_controller as ctrl
main = Blueprint('main', __name__)

@main.route("/")
def home():
    return ctrl.home()

@main.route("/menu")
def menu(): 
    return ctrl.menu()

@main.route("/reservations", methods=["GET", "POST"])
def reservations():
    return ctrl.reservations()

@main.route("/about")
def about():
    return ctrl.about()

@main.route("/contactus", methods=["GET", "POST"])
def contact():
    return ctrl.contact()