from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "live": True, "ready": True}

@router.get("/health/live")
def health_live():
    return {"status": "alive"}

@router.get("/health/ready")
def health_ready():
    return {"status": "ready"}