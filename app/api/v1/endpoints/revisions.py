from fastapi import APIRouter

router = APIRouter()

# Placeholder for revision endpoints
@router.get("/")
async def list_revisions():
    """修正案一覧取得（未実装）"""
    return {"message": "Revision endpoints not yet implemented"}


@router.post("/")
async def create_revision():
    """修正案作成（未実装）"""
    return {"message": "Revision creation endpoint not yet implemented"}