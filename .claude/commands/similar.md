---
name: similar
description: Find similar past setups for a scan result via RAG. Usage: /similar <result_id> <user_id>
---

Find historically similar catalyst setups for a given scan result using pgvector RAG search.

Arguments: $ARGUMENTS (format: "result_id user_id")

Steps:
1. Parse result_id and user_id from arguments
2. Run the RAG similarity agent:

```python
import asyncio, sys
sys.path.insert(0, "apps/api")
from app.agents.rag_similarity import find_similar

args = "$ARGUMENTS".split()
if len(args) < 2:
    print("Usage: /similar <result_id> <user_id>")
    exit(1)

result_id, user_id = args[0], args[1]
limit = int(args[2]) if len(args) > 2 else 5

results = asyncio.run(find_similar(result_id, user_id, limit=limit))
if not results:
    print("No similar setups found.")
else:
    print(f"\nFound {len(results)} similar setup(s):\n")
    for r in results:
        sim = r.get("similarity", 0)
        print(f"  {r['ticker']:8} | {sim:.2%} match | {r.get('trading_signal','?'):12} | {r.get('analysis_text','')[:80]}...")
```
