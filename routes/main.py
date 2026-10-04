from flask import Blueprint
from decorators import login_required
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

@main.route("/ai-assistant", methods=["GET", "POST"])
@login_required
def ai_assistant():
    from controllers.assistant_controller import assistant
    return assistant()

@main.route("/ai-assistant/new")
@login_required
def new_ai_chat():
    return ctrl.new_ai_chat()

@main.route("/ai-assistant/<int:chat_id>/delete", methods=["POST"])
@login_required
def delete_ai_chat(chat_id):
    return ctrl.delete_ai_chat(chat_id)
