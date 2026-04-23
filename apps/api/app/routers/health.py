from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@router.get("/metrics")
async def metrics():
    """Basic runtime metrics — extend with Prometheus if needed."""
    import psutil
    proc = psutil.Process()
    return {
        "cpu_percent": proc.cpu_percent(),
        "memory_mb": proc.memory_info().rss / 1024 / 1024,
        "threads": proc.num_threads(),
    }
