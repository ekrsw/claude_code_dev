from fastapi import APIRouter

router = APIRouter()

# Placeholder for article endpoints
@router.get("/")
async def list_articles():
    """記事一覧取得（未実装）"""
    return {"message": "Article endpoints not yet implemented"}


@router.get("/{article_id}")
async def get_article(article_id: str):
    """記事詳細取得（未実装）"""
    return {"message": f"Article {article_id} endpoint not yet implemented"}