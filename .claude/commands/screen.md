---
name: screen
description: Convert natural language to a screener config. Usage: /screen "scan premarket gainers over 5% with small cap"
---

Convert natural language screening criteria into a TradingView screener config using the Episodic Pivot screener config producer agent.

User input: $ARGUMENTS

Steps:
1. Call the screener config producer agent with the user's input:

```python
import asyncio, sys
sys.path.insert(0, "apps/api")
from app.agents.screener_config_producer import produce_config_stream

async def run():
    full = ""
    final = None
    async for chunk in produce_config_stream("$ARGUMENTS"):
        if chunk["type"] == "chunk":
            print(chunk["text"], end="", flush=True)
            full += chunk["text"]
        elif chunk["type"] == "final":
            final = chunk
    print()
    if final and final.get("success") and final.get("config"):
        import json
        print("\n✓ Config ready:")
        print(json.dumps(final["config"], indent=2))
    elif final:
        print(f"\n✗ {final.get('message', 'Could not build config')}")
        if final.get("missing_criteria"):
            print("Missing:", ", ".join(final["missing_criteria"]))

asyncio.run(run())
```
