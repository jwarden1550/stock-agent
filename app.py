import os
import yfinance as yf
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from agent import run_agent, get_stock_quote, get_price_history
from db import (init_db, create_user, get_user_by_email, get_user_by_id,
                verify_password, save_report, get_reports, delete_report,
                get_watchlist_tickers, add_to_watchlist, remove_from_watchlist,
                get_portfolio, add_position, update_position, delete_position)
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
                "cost_per_share": float(p.get("cost_per_share") or 0),
                "purchased_at": str(p["purchased_at"]) if p.get("purchased_at") else None,
                "name": quote.get("name"),
                "price": quote.get("price"),
                "change_percent": quote.get("change_percent"),
                "perf": perf.get("30d_performance_percent"),
            })
        except Exception:
            results.append({"id": p["id"], "ticker": p["ticker"], "shares": float(p["shares"]),
                            "cost_per_share": float(p.get("cost_per_share") or 0),
                            "purchased_at": str(p["purchased_at"]) if p.get("purchased_at") else None,
                            "name": None, "price": None, "change_percent": None, "perf": None})
    return jsonify(results)

PERIOD_MAP = {
    "1d":  ("1d",  "5m"),
    "1wk": ("5d",  "1h"),
    "1m":  ("1mo", "1d"),
    "3m":  ("3mo", "1d"),
    "6m":  ("6mo", "1d"),
    "1y":  ("1y",  "1d"),
    "ytd": ("ytd", "1d"),
    "5y":  ("5y",  "1wk"),
    "10y": ("10y", "1mo"),
    "all": ("max", "1mo"),
}

@app.route("/portfolio/add", methods=["POST"])
@login_required
def portfolio_add():
    data = request.get_json()
    ticker = data.get("ticker", "").strip().upper()
    shares = data.get("shares")
    total_cost_basis = data.get("total_cost_basis", 0)
    if not ticker:
        return jsonify({"error": "Ticker is required."}), 400
    try:
        shares = float(shares)
        if shares <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number of shares."}), 400
    try:
        total_cost_basis = float(total_cost_basis) if total_cost_basis else 0
        if total_cost_basis < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid cost basis."}), 400
    info = yf.Ticker(ticker).info
    if not info or (not info.get("regularMarketPrice") and not info.get("currentPrice")):
        return jsonify({"error": f"Could not find ticker '{ticker}'."}), 400
    cost_per_share = total_cost_basis / shares if shares else 0
    purchased_at = data.get("purchased_at") or None
    add_position(current_user.id, ticker, shares, cost_per_share, purchased_at)
    return jsonify({"ok": True})

@app.route("/portfolio/<int:position_id>", methods=["PUT"])
@login_required
def portfolio_edit(position_id):
    data = request.get_json()
    shares = data.get("shares")
    total_cost_basis = data.get("total_cost_basis", 0)
    purchased_at = data.get("purchased_at") or None
    try:
        shares = float(shares)
        if shares <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number of shares."}), 400
    try:
        total_cost_basis = float(total_cost_basis) if total_cost_basis else 0
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid cost basis."}), 400
    cost_per_share = total_cost_basis / shares if shares else 0
    update_position(position_id, current_user.id, shares, cost_per_share, purchased_at)
    return jsonify({"ok": True})

from datetime import date as _date, timedelta as _timedelta

def _period_start(period_key):
    today = _date.today()
    return {
        "1d":  today - _timedelta(days=1),
        "1wk": today - _timedelta(weeks=1),
        "1m":  today - _timedelta(days=30),
        "3m":  today - _timedelta(days=90),
        "6m":  today - _timedelta(days=180),
        "1y":  today - _timedelta(days=365),
        "ytd": _date(today.year, 1, 1),
        "5y":  today - _timedelta(days=365*5),
        "10y": today - _timedelta(days=365*10),
    }.get(period_key)  # returns None for "all"

def _interval_for_days(days):
    if days <= 5:   return "5m"
    if days <= 730: return "1d"
    return "1wk"

def _fetch_hist(ticker, period_key, purchased_at=None):
    if period_key == "all" and purchased_at:
        return yf.Ticker(ticker).history(start=str(purchased_at), interval="1d")
    yf_period, yf_interval = PERIOD_MAP.get(period_key, ("1mo", "1d"))
    return yf.Ticker(ticker).history(period=yf_period, interval=yf_interval)

@app.route("/portfolio/chart")
@login_required
def portfolio_total_chart():
    period_key = request.args.get("period", "1m")
    positions = get_portfolio(current_user.id)
    if not positions:
        return jsonify([])

    # Earliest purchase date across all positions
    purchase_dates = [p["purchased_at"] for p in positions if p.get("purchased_at")]
    min_purchased = min(purchase_dates) if purchase_dates else None

    # Period's natural start date (None means "all time")
    period_start = _period_start(period_key)

    # If the user bought more recently than the period start, or period is "all",
    # anchor the chart to the purchase date instead
    if min_purchased and (period_start is None or min_purchased > period_start):
        start_str = str(min_purchased)
        days = (_date.today() - min_purchased).days
        interval = _interval_for_days(days)
        def get_hist(ticker): return yf.Ticker(ticker).history(start=start_str, interval=interval)
    else:
        yf_period, yf_interval = PERIOD_MAP.get(period_key, ("1mo", "1d"))
        def get_hist(ticker): return yf.Ticker(ticker).history(period=yf_period, interval=yf_interval)

    combined = None
    for p in positions:
        shares = float(p["shares"])
        hist = get_hist(p["ticker"])
        if hist.empty:
            continue
        series = (hist["Close"] * shares).rename(p["ticker"])
        combined = series.to_frame() if combined is None else combined.join(series, how="outer")
    if combined is None:
        return jsonify([])
    combined = combined.ffill()
    combined["total"] = combined.sum(axis=1)
    return jsonify([
        {"date": str(d), "value": round(float(row["total"]), 2)}
        for d, row in combined.iterrows()
    ])

@app.route("/portfolio/chart/<int:position_id>")
@login_required
def portfolio_position_chart(position_id):
    period_key = request.args.get("period", "1m")
    positions = get_portfolio(current_user.id)
    pos = next((p for p in positions if p["id"] == position_id), None)
    if not pos:
        return jsonify({"error": "Not found"}), 404
    hist = _fetch_hist(pos["ticker"], period_key, pos.get("purchased_at"))
    if hist.empty:
        return jsonify({"error": "No data"}), 404
    shares = float(pos["shares"])
    return jsonify([
        {"date": str(d), "value": round(float(c) * shares, 2)}
        for d, c in zip(hist.index, hist["Close"])
    ])

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
