from datetime import datetime, timedelta
from typing import Optional
from functools import wraps
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from sqlalchemy import text
from app.repositories.db_repository import SessionLocal

# Настройки JWT
SECRET_KEY = "your_super_secret_key_change_in_production_vkr_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


# Pydantic модели
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля с использованием bcrypt напрямую"""
    try:
        password_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Хеширование пароля с использованием bcrypt напрямую"""
    try:
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"Error hashing password: {e}")
        raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with SessionLocal() as session:
        result = session.execute(
            text("SELECT id, username, email, role FROM users WHERE username = :username"),
            {"username": username}
        )
        user = result.fetchone()
        if user is None:
            raise credentials_exception
        return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}


def require_role(required_role: str):
    """Декоратор для проверки роли пользователя"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            if current_user.get("role") != required_role:
                raise HTTPException(
                    status_code=403,
                    detail=f"Доступ запрещен. Требуется роль: {required_role}"
                )
            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator