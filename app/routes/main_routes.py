from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/login")
def login_page():
    return render_template("login.html")


@main_bp.route("/builder")
def builder():
    return render_template("builder.html")


@main_bp.route("/view/<int:board_id>")
def view(board_id):
    return render_template("view.html", board_id=board_id)
