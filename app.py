import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from agent import run_agent
from db import init_db, create_user, get_user_by_email, get_user_by_id, verify_password, save_report, get_reports
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

init_db()

class User(UserMixin):
    def __init__(self, data):
        self.id = data["id"]
        self.email = data["email"]

@login_manager.user_loader
def load_user(user_id):
    data = get_user_by_id(int(user_id))
    return User(data) if data else None

# ---------- Auth routes ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            return render_template("register.html", error="All fields are required.")
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.")
        if get_user_by_email(email):
            return render_template("register.html", error="An account with that email already exists.")
        try:
            user_id = create_user(email, password)
            data = get_user_by_id(user_id)
            login_user(User(data))
            return redirect(url_for("index"))
        except Exception:
            return render_template("register.html", error="Something went wrong. Please try again.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user_data = get_user_by_email(email)
        if not user_data or not verify_password(password, user_data["password_hash"]):
            return render_template("login.html", error="Invalid email or password.")
        login_user(User(user_data))
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------- App routes ----------

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/research", methods=["POST"])
@login_required
def research():
    data = request.get_json()
    goal = data.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "Please enter a research goal."}), 400
    report, tool_calls = run_agent(goal)
    report_id = save_report(goal, report, tool_calls, user_id=current_user.id)
    return jsonify({"report": report, "tool_calls": tool_calls, "id": report_id})

@app.route("/reports", methods=["GET"])
@login_required
def reports():
    return jsonify(get_reports(user_id=current_user.id))

if __name__ == "__main__":
    app.run(debug=True, port=5001)
