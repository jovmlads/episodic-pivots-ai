"""
One-time Langfuse setup: push system prompt + sync dataset from Supabase.

Usage (from apps/api):
  python -m scripts.langfuse_setup

Requires env vars: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL,
                   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations
import base64
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

LANGFUSE_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LANGFUSE_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
LANGFUSE_BASE_URL = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

_LF_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(
        f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    ).decode(),
    "Content-Type": "application/json",
}
_SB_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}

DATASET_NAME = "news_analyser_production"
PROMPT_NAME = "news_analyser"


def _lf_post(path: str, payload: dict) -> dict:
    r = httpx.post(f"{LANGFUSE_BASE_URL}{path}", json=payload, headers=_LF_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def push_prompt() -> None:
    from app.agents.news_analyser import SYSTEM_PROMPT
    print(f"Pushing prompt '{PROMPT_NAME}' to Langfuse...")
    try:
        result = _lf_post("/api/public/v2/prompts", {
            "name": PROMPT_NAME,
            "prompt": SYSTEM_PROMPT,
            "type": "text",
            "labels": ["production"],
        })
        print(f"  Created version {result.get('version')}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            print("  Already exists — no change")
        else:
            raise


def create_dataset() -> None:
    print(f"Creating dataset '{DATASET_NAME}'...")
    try:
        _lf_post("/api/public/v2/datasets", {
            "name": DATASET_NAME,
            "description": "Production ai_analyses from Supabase",
        })
        print("  Created")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            print("  Already exists — will append items")
        else:
            raise


def sync_dataset(limit: int = 200) -> None:
    print(f"Fetching {limit} most recent analyses from Supabase...")
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/ai_analyses",
        params={
            "select": "id,result_id,catalyst_type,sentiment,trading_signal,analysis_text,web_search_used,tokens_input,tokens_output",
            "order": "created_at.desc",
            "limit": limit,
        },
        headers=_SB_HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    analyses = r.json()
    if not analyses:
        print("  No analyses found")
        return

    result_ids = [a["result_id"] for a in analyses if a.get("result_id")]
    r2 = httpx.get(
        f"{SUPABASE_URL}/rest/v1/scan_results",
        params={
            "select": "id,ticker,premarket_change_pct",
            "id": f"in.({','.join(result_ids)})",
        },
        headers=_SB_HEADERS,
        timeout=30,
    )
    r2.raise_for_status()
    scan_map = {row["id"]: row for row in r2.json()}

    print(f"  Uploading {len(analyses)} items...")
    ok = 0
    for a in analyses:
        scan = scan_map.get(a.get("result_id"), {})
        try:
            _lf_post("/api/public/v2/dataset-items", {
                "datasetName": DATASET_NAME,
                "input": {
                    "ticker": scan.get("ticker", "UNKNOWN"),
                    "premarket_change_pct": scan.get("premarket_change_pct"),
                },
                "expectedOutput": {
                    "trading_signal": a["trading_signal"],
                    "catalyst_type": a["catalyst_type"],
                    "sentiment": a["sentiment"],
                    "analysis_text": a["analysis_text"],
                },
                "metadata": {
                    "web_search_used": a["web_search_used"],
                    "tokens_input": a["tokens_input"],
                    "tokens_output": a["tokens_output"],
                    "source_analysis_id": a["id"],
                },
            })
            ok += 1
        except Exception as exc:
            print(f"    Skipped {a['id']}: {exc}")
    print(f"  Done — {ok}/{len(analyses)} uploaded")


if __name__ == "__main__":
    push_prompt()
    create_dataset()
    sync_dataset(limit=int(sys.argv[1]) if len(sys.argv) > 1 else 200)
    print("\nDone. Next steps:")
    print("  Prompts  → langfuse.com → Prompts → edit 'news_analyser' in the UI")
    print("  Datasets → langfuse.com → Datasets → 'news_analyser_production'")
    print("  Evals    → langfuse.com → LLM-as-a-Judge → create evaluator (see README)")
