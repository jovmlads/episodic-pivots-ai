---
name: analyse
description: "Run AI catalyst analysis for a ticker against today's news. Usage: /analyse TICKER [pm_change%]"
---

Run news catalyst analysis for the given ticker using the Episodic Pivot news analyser agent.

Arguments: $ARGUMENTS (format: "TICKER [pm_change_pct]", e.g. "AAPL 5.2")

Steps:
1. Parse ticker and optional premarket_change_pct from arguments (default 0.0 if not provided)
2. Call the news analyser agent directly:

```python
import asyncio, sys
sys.path.insert(0, "apps/api")
from app.agents.news_analyser import analyse_ticker

args = "$ARGUMENTS".split()
ticker = args[0].upper() if args else "UNKNOWN"
pct = float(args[1]) if len(args) > 1 else 0.0

result = asyncio.run(analyse_ticker(
    ticker=ticker,
    company_name=ticker,
    premarket_change_pct=pct,
    news_url=None,
))
print(f"\n{'='*50}")
print(f"Ticker:   {ticker}")
print(f"PM Move:  {pct:+.1f}%")
print(f"Catalyst: {result.catalyst_type}")
print(f"Signal:   {result.trading_signal.upper()}")
print(f"Sentiment:{result.sentiment}")
print(f"\n{result.analysis_text}")
print(f"\nTokens: {result.tokens_input + result.tokens_output} (web_search={result.web_search_used})")
```
