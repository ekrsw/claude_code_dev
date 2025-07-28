from enum import Enum


class Role(str, Enum):
    """User roles"""
    GENERAL = "general"
    SUPERVISOR = "supervisor"
    APPROVER = "approver"
    ADMIN = "admin"


class RevisionStatus(str, Enum):
    """Revision status"""
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApprovalAction(str, Enum):
    """Approval action types"""
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class NotificationType(str, Enum):
    """Notification types"""
    REVISION_CREATED = "revision_created"
    REVISION_SUBMITTED = "revision_submitted"
    REVISION_EDITED = "revision_edited"
    REVISION_APPROVED = "revision_approved"
    REVISION_REJECTED = "revision_rejected"
    REVISION_REQUEST = "revision_request"
    COMMENT_ADDED = "comment_added"


class Priority(str, Enum):
    """Priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Target(str, Enum):
    """Article target audience"""
    INTERNAL = "社内向け"
    EXTERNAL = "社外向け"
    NOT_APPLICABLE = "対象外"