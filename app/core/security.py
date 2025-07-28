from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
import uuid

from passlib.context import CryptContext
from passlib.hash import bcrypt
from jose import JWTError, jwt
import structlog

from app.core.config import settings
from app.core.exceptions import AuthenticationError

logger = structlog.get_logger()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Password verification error", error=str(e))
        return False


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength according to policy"""
    errors = []
    
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
    
    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if settings.PASSWORD_REQUIRE_DIGITS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
    
    if settings.PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }


def create_access_token(
    subject: Union[str, Any], 
    user_id: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Generate JTI (JWT ID) for token blacklisting
    jti = str(uuid.uuid4())
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "user_id": user_id,
        "jti": jti,
        "type": "access"
    }
    
    try:
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error("JWT encoding error", error=str(e))
        raise AuthenticationError("Failed to create access token")


def create_refresh_token(
    subject: Union[str, Any],
    user_id: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT refresh token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    jti = str(uuid.uuid4())
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "user_id": user_id,
        "jti": jti,
        "type": "refresh"
    }
    
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error("JWT encoding error", error=str(e))
        raise AuthenticationError("Failed to create refresh token")


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Check token type
        token_type = payload.get("type")
        if token_type not in ["access", "refresh"]:
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            return None
        
        return payload
    except JWTError as e:
        logger.debug("JWT verification failed", error=str(e))
        return None
    except Exception as e:
        logger.error("Unexpected error in token verification", error=str(e))
        return None


def extract_token_from_header(authorization: str) -> Optional[str]:
    """Extract token from Authorization header"""
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        return token
    except ValueError:
        return None


def is_token_expired(token: str) -> bool:
    """Check if token is expired"""
    payload = verify_token(token)
    if not payload:
        return True
    
    exp = payload.get("exp")
    if not exp:
        return True
    
    return datetime.utcnow().timestamp() > exp


def get_token_jti(token: str) -> Optional[str]:
    """Get JTI from token for blacklisting"""
    payload = verify_token(token)
    if not payload:
        return None
    return payload.get("jti")