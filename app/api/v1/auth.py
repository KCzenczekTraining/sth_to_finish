import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..auth import (
    Token, UserLogin, UserRegistration, UserResponse,
    create_token, hash_password, verify_password, 
    is_strong_password, clean_input, security, verify_token
)
from ..database import User, get_db

router = APIRouter()

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Session = Depends(get_db)
) -> User:
    user_id = verify_token(credentials)
    user = db.query(User).filter(User.user_id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserRegistration, db: Session = Depends(get_db)):
    user_id = clean_input(user_data.user_id)
    email = clean_input(user_data.email.lower())
    
    if len(user_id) < 3 or not re.match(r'^[a-zA-Z0-9_-]+$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    
    if not is_strong_password(user_data.password):
        raise HTTPException(status_code=400, detail="Password too weak")
    
    if db.query(User).filter((User.user_id == user_id) | (User.email == email)).first():
        raise HTTPException(status_code=400, detail="User already exists")
    
    try:
        user = User(
            user_id=user_id,
            email=email,
            hashed_password=hash_password(user_data.password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return UserResponse(**user.to_dict())
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=Token)
async def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == clean_input(login_data.user_id)).first()
    
    if not user or not user.is_active or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token({"sub": user.user_id})
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.to_dict())
