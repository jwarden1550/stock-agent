import os
import yfinance as yf
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from agent import run_agent, get_stock_quote, get_price_history
from db import (init_db, create_user, get_user_by_email, get_user_by_id,
                verify_password, save_report, get_reports, delete_report,
                get_watchlist_tickers, add_to_watchlist, remove_from_watchlist,
                get_portfolio, add_position, delete_position)
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

# ---------- Auth ----------

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
            login_user(User(get_user_by_id(user_id)))
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

# ---------- Pages ----------

@app.route("/")
@login_required
def index():
    return render_template("index.html", active="research")

@app.route("/history")
@login_required
def history():
    return render_template("history.html", active="history")

@app.route("/watchlist")
@login_required
def watchlist():
    return render_template("watchlist.html", active="watchlist")

@app.route("/chart")
@login_required
def chart():
    return render_template("chart.html", active="chart")

@app.route("/portfolio")
@login_required
def portfolio():
    return render_template("portfolio.html", active="portfolio")

# ---------- Research API ----------

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

# ---------- Reports API ----------

@app.route("/reports")
@login_required
def reports():
    return jsonify(get_reports(user_id=current_user.id))

@app.route("/reports/<int:report_id>", methods=["DELETE"])
@login_required
def delete_report_route(report_id):
    delete_report(report_id, current_user.id)
    return jsonify({"ok": True})

# ---------- Watchlist API ----------

@app.route("/watchlist/data")
@login_required
def watchlist_data():
    tickers = get_watchlist_tickers(current_user.id)
    results = []
    for ticker in tickers:
        try:
            quote = get_stock_quote(ticker)
            perf = get_price_history(ticker)
            results.append({
                "ticker": ticker,
                "name": quote.get("name"),
                "price": quote.get("price"),
                "change_percent": quote.get("change_percent"),
                "perf": perf.get("30d_performance_percent"),
            })
        except Exception:
            results.append({"ticker": ticker, "name": None, "price": None, "change_percent": None, "perf": None})
    return jsonify(results)

@app.route("/watchlist/add", methods=["POST"])
@login_required
def watchlist_add():
    data = request.get_json()
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker is required."}), 400
    info = yf.Ticker(ticker).info
    if not info or not info.get("regularMarketPrice") and not info.get("currentPrice"):
        return jsonify({"error": f"Could not find ticker '{ticker}'."}), 400
    add_to_watchlist(current_user.id, ticker)
    return jsonify({"ok": True})

@app.route("/watchlist/<ticker>", methods=["DELETE"])
@login_required
def watchlist_remove(ticker):
    remove_from_watchlist(current_user.id, ticker.upper())
    return jsonify({"ok": True})

# ---------- Portfolio API ----------

@app.route("/portfolio/data")
@login_required
def portfolio_data():
    positions = get_portfolio(current_user.id)
    results = []
    for p in positions:
        try:
            quote = get_stock_quote(p["ticker"])
            perf = get_price_history(p["ticker"])
            results.append({
                "id": p["id"],
                "ticker": p["ticker"],
                "shares": float(p["shares"]),
                "name": quote.get("name"),
                "price": quote.get("price"),
                "change_percent": quote.get("change_percent"),
                "perf": perf.get("30d_performance_percent"),
            })
        except Exception:
            results.append({"id": p["id"], "ticker": p["ticker"], "shares": float(p["shares"]),
                            "name": None, "price": None, "change_percent": None, "perf": None})
    return jsonify(results)

@app.route("/portfolio/add", methods=["POST"])
@login_required
def portfolio_add():
    data = request.get_json()
    ticker = data.get("ticker", "").strip().upper()
    shares = data.get("shares")
    if not ticker:
        return jsonify({"error": "Ticker is required."}), 400
    try:
        shares = float(shares)
        if shares <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number of shares."}), 400
    info = yf.Ticker(ticker).info
    if not info or (not info.get("regularMarketPrice") and not info.get("currentPrice")):
        return jsonify({"error": f"Could not find ticker '{ticker}'."}), 400
    add_position(current_user.id, ticker, shares)
    return jsonify({"ok": True})

@app.route("/portfolio/<int:position_id>", methods=["DELETE"])
@login_required
def portfolio_delete(position_id):
    delete_position(position_id, current_user.id)
    return jsonify({"ok": True})

# ---------- Chart API ----------

@app.route("/api/prices/<ticker>")
@login_required
def api_prices(ticker):
    hist = yf.Ticker(ticker.upper()).history(period="1mo")
    if hist.empty:
        return jsonify({"error": f"No price data found for '{ticker}'."}), 404
    data = [{"date": str(d.date()), "close": round(float(c), 2)}
            for d, c in zip(hist.index, hist["Close"])]
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
