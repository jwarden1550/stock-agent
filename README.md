# Stock Research Agent

## Overview
This project I created is an AI agent that researches stocks on its own and puts together
professional investment research reports, almost like having a your own personal analyst that handle
this for you. Through this, I really wanted to understand how AI agents actually
work, from tool use to multi-step reasoning, and autonomous workflows that show
how an agent can take a task and carry it through from start to finish.

## What Makes This an Agent
Unlike a standard pipeline where you tell the code exactly what to do step by step,
this agent is given a goal in plain English and decides on its own which tools to call,
in what order, and when it has gathered enough information to write the final report.

Example:
- You type: "Compare Apple and Microsoft and tell me which is the better investment"
- The agent decides to call compare_stocks, then get_recent_news for each company,
  then get_price_history for both, then synthesizes everything into a final report
- You never tell it which tools to use or in what order

## Framework
I built it using Google Gemini's native function calling framework, which, in terms of
architecture, works the same way as tools like LangChain, CrewAI, and OpenAI Assistants.
The way it actually works is that the model is handed a set of tool definitions along
with the blueprints for how each one is used, and from there it decides on its own which
tools to invoke based on what the research goal happens to be.

## Tools Available to the Agent
The agent has 5 tools it can call autonomously:

1. get_stock_quote | Fetches current price, daily change, and volume
2. get_company_overview | Pulls fundamentals: PE ratio, market cap, EPS, revenue growth
3. get_recent_news | Gets latest news headlines for a stock
4. get_price_history | Calculates 30 day performance metrics
5. compare_stocks | Side by side fundamental comparison of two stocks

## How the Agent Loop Works
1. User provides a plain English goal
2. Agent decides which tools to call (Turn 1)
3. Tools return real data from Yahoo Finance
4. Agent reads results and decides next steps (Turn 2, 3...)
5. Agent determines it has enough data
6. Writes final professional report in Markdown
7. Report displayed in browser with tool call count

## Multi-Step Reasoning Example
For the goal "Compare Apple and Microsoft as investments":

1. Turn 1 — Agent calls compare_stocks(AAPL, MSFT)
2. Turn 2 — Agent calls get_recent_news(AAPL)
3. Turn 3 — Agent calls get_recent_news(MSFT)
4. Turn 4 — Agent calls get_stock_quote(AAPL)
5. Turn 5 — Agent calls get_stock_quote(MSFT)
6. Final — Agent writes comprehensive comparison report with verdict

All 5 steps decided autonomously with no manual intervention.

## Autonomous Capabilities
The agent can handle all of these goals without any additional instructions:
- "Research [stock] and give me a buy or sell recommendation"
- "Compare [stock 1] and [stock 2] as investments"
- "Should I invest in [stock] right now?"
- "What is the financial health of [company]?"
- "Which is the better long term investment, [stock 1] or [stock 2]?"

## How to Run
pip install -r requirements.txt

python3 app.py
Then open http://127.0.0.1:5001 in your browser.

## Tech Stack
- Python
- Flask (web interface)
- Google Gemini 2.5 Flash (agent reasoning engine)
- yfinance (real time stock data from Yahoo Finance)
- HTML/CSS (frontend)

## Data Sources
All financial data is pulled in real time from Yahoo Finance via the yfinance
library. This includes current prices, company fundamentals, analyst targets,
and recent news headlines.

## What I Learned
Building this agent taught me the real difference between a pipeline and an agent, which
was probably the biggest takeaway for me. A pipeline just follows a fixed path that you
lay out ahead of time, whereas an agent actually reasons through what steps to take based
on the goal and whatever data it finds along the way. The tool use framework is what makes
that possible. By handing the model a set of tools with clear descriptions, you give it
what it needs to plan and carry out multi-step workflows on its own.