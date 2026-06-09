from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config import settings
from app.middleware.auth import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> dict:
    if form.password != settings.trader_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_access_token()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expiry_hours * 3600,
    }


@router.post("/refresh")
async def refresh(current_user: str = Depends(get_current_user)) -> dict:
    token = create_access_token(sub=current_user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expiry_hours * 3600,
    }
