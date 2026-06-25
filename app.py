from flask import Flask, render_template, request, jsonify
from agent import run_agent
from db import init_db, save_report, get_reports

app = Flask(__name__)
init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/research", methods=["POST"])
def research():
    data = request.get_json()
    goal = data.get("goal", "").strip()

    if not goal:
        return jsonify({"error": "Please enter a research goal."}), 400

    report, tool_calls = run_agent(goal)
    report_id = save_report(goal, report, tool_calls)

    return jsonify({
        "report": report,
        "tool_calls": tool_calls,
        "id": report_id
    })

@app.route("/reports", methods=["GET"])
def reports():
    return jsonify(get_reports())

if __name__ == "__main__":
    app.run(debug=True, port=5001)
