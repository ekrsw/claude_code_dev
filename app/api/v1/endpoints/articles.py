from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.article import ArticleResponse, ArticleListResponse, ArticleFilter
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.article import ArticleService
from app.services.notification import NotificationService
from app.services.revision import RevisionService
from app.constants.enums import NotificationType

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ArticleListResponse])
async def list_articles(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="検索語句"),
    category: Optional[str] = Query(None, description="カテゴリフィルタ"),
    importance: Optional[bool] = Query(None, description="重要度フィルタ"),
    target: Optional[str] = Query(None, description="対象フィルタ"),
    is_active: Optional[bool] = Query(True, description="アクティブステータスフィルタ"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """記事一覧取得"""
    article_service = ArticleService(db)
    
    # フィルタパラメータ作成
    filter_params = ArticleFilter(
        search=search,
        category=category,
        importance=importance,
        target=target,
        is_active=is_active
    )
    
    # 記事検索
    if search:
        articles = await article_service.search_articles(search)
        total = len(articles)
    else:
        articles = await article_service.get_all_articles(skip=pagination.offset, limit=pagination.size)
        # TODO: 総数取得の実装が必要
        total = len(articles)
    
    return PaginatedResponse.create(
        items=articles,
        total=total,
        page=pagination.page,
        size=pagination.size
    )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """記事詳細取得"""
    article_service = ArticleService(db)
    
    # article_idがUUIDか文字列IDかを判定
    try:
        # UUIDとして解析を試みる
        uuid_id = UUID(article_id)
        article = await article_service.get_article_by_id(uuid_id)
    except ValueError:
        # UUIDでない場合は文字列IDとして検索
        # TODO: article_idによる検索メソッドの実装が必要
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    return article


@router.get("/{article_id}/revisions", response_model=List[dict])
async def get_article_revisions(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """記事に関連する修正案一覧取得"""
    revision_service = RevisionService(db)
    
    try:
        # article_idがUUIDか文字列IDかを判定
        try:
            uuid_id = UUID(article_id)
        except ValueError:
            # TODO: 文字列IDからUUIDへの変換が必要
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # 記事に関連する修正案を取得
        revisions = await revision_service.get_revisions_by_article(uuid_id)
        
        return revisions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{article_id}/watch")
async def watch_article(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """記事の監視を開始（記事に対する変更通知を受け取る）"""
    notification_service = NotificationService(db)
    
    try:
        # TODO: 記事監視機能の実装
        # 記事に対する修正案が作成された際に通知を送信する仕組みが必要
        return {"message": "Article watch feature not yet implemented"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{article_id}/watch")
async def unwatch_article(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """記事の監視を停止"""
    notification_service = NotificationService(db)
    
    try:
        # TODO: 記事監視解除機能の実装
        return {"message": "Article unwatch feature not yet implemented"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )