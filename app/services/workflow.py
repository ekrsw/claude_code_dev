from sqlalchemy.ext.asyncio import AsyncSession


class WorkflowService:
    """Workflow service (placeholder)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db