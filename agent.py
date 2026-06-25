import os
import json
import yfinance as yf
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def get_stock_quote(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    info = stock.info
    if not info:
        return {"error": f"No data found for {ticker}"}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev_close = info.get("previousClose") or price
    change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else None
    return {
        "ticker": ticker.upper(),
        "name": info.get("longName"),
        "price": price,
        "previous_close": prev_close,
        "day_high": info.get("dayHigh"),
        "day_low": info.get("dayLow"),
        "volume": info.get("volume"),
        "change_percent": change_pct,
    }

def get_company_overview(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    info = stock.info
    if not info:
        return {"error": f"No overview found for {ticker}"}
    return {
        "name": info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "dividend_yield": info.get("dividendYield"),
        "analyst_target": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
        "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "description": info.get("longBusinessSummary"),
    }

def get_recent_news(ticker: str) -> list:
    stock = yf.Ticker(ticker.upper())
    news = stock.news
    if not news:
        return [{"note": "No recent news found"}]
    results = []
    for article in news[:6]:
        content = article.get("content", article)
        provider = content.get("provider") or {}
        results.append({
            "title": content.get("title") or article.get("title"),
            "summary": content.get("summary") or article.get("summary"),
            "source": provider.get("displayName") or article.get("publisher"),
            "published": content.get("pubDate") or article.get("providerPublishTime"),
        })
    return results

def get_price_history(ticker: str) -> dict:
    hist = yf.Ticker(ticker.upper()).history(period="1mo")
    if hist.empty:
        return {"error": f"No price history found for {ticker}"}
    start_price = hist["Close"].iloc[0]
    end_price = hist["Close"].iloc[-1]
    performance_30d = round(((end_price - start_price) / start_price) * 100, 2)
    return {
        "ticker": ticker,
        "30d_performance_percent": performance_30d,
        "30d_high": round(hist["High"].max(), 2),
        "30d_low": round(hist["Low"].min(), 2),
        "current_price": round(end_price, 2),
        "avg_daily_volume_30d": round(hist["Volume"].mean(), 0),
    }

def compare_stocks(ticker1: str, ticker2: str) -> dict:
    overview1 = get_company_overview(ticker1)
    overview2 = get_company_overview(ticker2)
    perf1 = get_price_history(ticker1)
    perf2 = get_price_history(ticker2)
    return {
        "stock_1": {**overview1, "ticker": ticker1, "performance": perf1},
        "stock_2": {**overview2, "ticker": ticker2, "performance": perf2},
        "comparison_note": f"Direct comparison between {ticker1} and {ticker2}"
    }

# --------------------------------------------------------------------------
# Tool definitions (OpenAI-compatible format)
# --------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Get current stock price and trading data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_overview",
            "description": "Get company fundamentals including PE ratio, market cap, revenue growth, and analyst target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_news",
            "description": "Get recent news headlines for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": "Get 30 day price history and performance metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": "Compare two stocks side by side.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker1": {"type": "string", "description": "First stock ticker symbol"},
                    "ticker2": {"type": "string", "description": "Second stock ticker symbol"}
                },
                "required": ["ticker1", "ticker2"]
            }
        }
    },
]

SYSTEM_PROMPT = """You are a professional stock market analyst agent with 20 years of experience.

You have tools to look up current stock prices, company fundamentals, recent news,
30 day price history, and compare stocks side by side.

How to work:
- Break the user's goal into steps and call the right tools to gather what you need.
- Always get both the quote AND the overview for any stock you are researching.
- For comparisons, use compare_stocks first, then get recent news for each stock.
- Ground every claim in the data returned by your tools.
- When you have enough data, write a final professional research report in Markdown.
- End every report with a clear Verdict section with a rating:
  Strong Buy / Buy / Hold / Sell / Strong Sell
"""

# --------------------------------------------------------------------------
# Tool dispatcher
# --------------------------------------------------------------------------

def dispatch(tool_name: str, tool_args: dict):
    if tool_name == "get_stock_quote":
        return get_stock_quote(**tool_args)
    if tool_name == "get_company_overview":
        return get_company_overview(**tool_args)
    if tool_name == "get_recent_news":
        return get_recent_news(**tool_args)
    if tool_name == "get_price_history":
        return get_price_history(**tool_args)
    if tool_name == "compare_stocks":
        return compare_stocks(**tool_args)
    return {"error": f"Unknown tool: {tool_name}"}

# --------------------------------------------------------------------------
# Agent loop
# --------------------------------------------------------------------------

def run_agent(goal: str, max_turns: int = 10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]
    tool_call_count = 0

    for turn in range(1, max_turns + 1):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            return message.content, tool_call_count

        for tc in message.tool_calls:
            tool_call_count += 1
            args = json.loads(tc.function.arguments)
            print(f"  Turn {turn}: calling {tc.function.name}({args})")
            result = dispatch(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return "Agent stopped: reached maximum turns.", tool_call_count
