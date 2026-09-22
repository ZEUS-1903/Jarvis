from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check: 'is the process up and serving HTTP?'"""
    return {"status": "ok"}
