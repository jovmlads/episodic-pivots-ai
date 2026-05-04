"""
RAG Similarity agent.
Embeds analysis text via OpenAI text-embedding-3-small,
then searches pgvector for similar past setups.
"""
from __future__ import annotations
import logging

from langfuse.openai import AsyncOpenAI

from app.config import settings
from app.database import get_supabase

logger = logging.getLogger(__name__)
oai = AsyncOpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


async def embed_text(text: str) -> list[float]:
    """Generate embedding vector for text."""
    response = await oai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8000],
        dimensions=EMBEDDING_DIMS,
    )
    return response.data[0].embedding


async def find_similar(
    result_id: str,
    user_id: str,
    limit: int = 5,
) -> list[dict]:
    """
    Find similar past analyses for a given scan result.
    Returns up to `limit` results, deduplicated by ticker.
    """
    db = get_supabase()

    # Get the analysis and source ticker for this result
    analysis_row = (
        db.table("ai_analyses")
        .select("id, analysis_text, embedding")
        .eq("result_id", result_id)
        .limit(1)
        .execute()
    )
    if not analysis_row.data:
        return []
    analysis = analysis_row.data[0]

    source_result = (
        db.table("scan_results")
        .select("ticker")
        .eq("id", result_id)
        .limit(1)
        .execute()
    )
    source_ticker: str | None = source_result.data[0]["ticker"] if source_result.data else None
    if not analysis.get("embedding"):
        # Generate embedding on demand if missing
        try:
            vector = await embed_text(analysis["analysis_text"])
            db.table("ai_analyses").update({"embedding": vector}).eq("id", analysis["id"]).execute()
            embedding = vector
        except Exception:
            logger.exception("Failed to generate embedding for result %s", result_id)
            return []
    else:
        embedding = analysis["embedding"]

    # pgvector cosine similarity search via Supabase RPC
    # Requires a DB function — see migration 002
    try:
        similar = db.rpc(
            "match_analyses",
            {
                "query_embedding": embedding,
                "user_id_filter": user_id,
                "exclude_analysis_id": analysis["id"],
                "match_count": limit * 4,  # fetch extra for dedup + filtering
            },
        ).execute()

        rows = similar.data or []
        # Filter: exclude the source ticker and apply similarity threshold
        SIMILARITY_THRESHOLD = 0.55
        seen_tickers: set[str] = set()
        if source_ticker:
            seen_tickers.add(source_ticker)
        results = []
        for row in rows:
            if row.get("similarity", 0) < SIMILARITY_THRESHOLD:
                continue
            ticker = row.get("ticker")
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                results.append(row)
            if len(results) >= limit:
                break
        return results
    except Exception:
        logger.exception("pgvector similarity search failed for result %s", result_id)
        return []
