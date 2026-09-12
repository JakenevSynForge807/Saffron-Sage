from flask import Blueprint
import controllers.auth_controller as ctrl
auth = Blueprint('auth', __name__)

@auth.route("/signup", methods=["GET", "POST"])
def signup():
    return ctrl.signup()

@auth.route("/login", methods=["GET", "POST"])
def login():
    return ctrl.login()
    

@auth.route("/logout")
def logout():
    return ctrl.logout()