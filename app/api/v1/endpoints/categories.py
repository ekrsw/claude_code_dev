from fastapi import APIRouter

router = APIRouter()

# Placeholder for category endpoints
@router.get("/")
async def list_categories():
    """カテゴリ一覧取得（未実装）"""
    return {"message": "Category endpoints not yet implemented"}