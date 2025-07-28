from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.db.base_model import BaseModel

logger = structlog.get_logger()

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations"""
    
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record"""
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance
    
    async def get(self, id: Union[UUID, str, int]) -> Optional[ModelType]:
        """Get record by ID"""
        return await self.db.get(self.model, id)
    
    async def get_by_field(
        self, 
        field_name: str, 
        value: Any,
        load_relationships: Optional[List[str]] = None
    ) -> Optional[ModelType]:
        """Get record by field value"""
        query = select(self.model).where(getattr(self.model, field_name) == value)
        
        if load_relationships:
            for rel in load_relationships:
                query = query.options(selectinload(getattr(self.model, rel)))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        load_relationships: Optional[List[str]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination"""
        query = select(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            query = query.order_by(getattr(self.model, order_by))
        else:
            query = query.order_by(self.model.created_at.desc())
        
        # Apply relationships loading
        if load_relationships:
            for rel in load_relationships:
                if hasattr(self.model, rel):
                    query = query.options(selectinload(getattr(self.model, rel)))
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters"""
        query = select(func.count(self.model.id))
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def update(
        self, 
        id: Union[UUID, str, int], 
        **kwargs
    ) -> Optional[ModelType]:
        """Update record by ID"""
        # Remove None values
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        
        if not update_data:
            return await self.get(id)
        
        query = (
            update(self.model)
            .where(self.model.id == id)
            .values(**update_data)
            .returning(self.model)
        )
        
        result = await self.db.execute(query)
        updated_instance = result.scalar_one_or_none()
        
        if updated_instance:
            await self.db.refresh(updated_instance)
        
        return updated_instance
    
    async def delete(self, id: Union[UUID, str, int]) -> bool:
        """Delete record by ID"""
        query = delete(self.model).where(self.model.id == id)
        result = await self.db.execute(query)
        return result.rowcount > 0
    
    async def exists(self, id: Union[UUID, str, int]) -> bool:
        """Check if record exists"""
        query = select(self.model.id).where(self.model.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def exists_by_field(self, field_name: str, value: Any) -> bool:
        """Check if record exists by field value"""
        query = select(self.model.id).where(getattr(self.model, field_name) == value)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None