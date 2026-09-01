"""Photographer registration, login and identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import current_user
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.schemas.common import ErrorDetail
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a photographer account",
    responses={
        409: {"model": ErrorDetail, "description": "Email already registered"},
        422: {"model": ErrorDetail, "description": "Validation failed"},
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Register and sign in immediately.

    Passwords are stored as bcrypt hashes; the plain value is never persisted
    or logged.
    """
    email = payload.email.lower().strip()
    existing = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )

    user = User(name=payload.name, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        ) from None
    db.refresh(user)
    return _token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in and receive a JWT",
    responses={401: {"model": ErrorDetail, "description": "Invalid credentials"}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange email and password for a bearer token."""
    user = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower().strip())
    ).scalar_one_or_none()

    # Same message and comparable timing whether the email or the password was
    # wrong, so the endpoint cannot be used to enumerate accounts.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled"
        )
    return _token_response(user)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current photographer",
    responses={401: {"model": ErrorDetail, "description": "Missing or invalid token"}},
)
def me(user: User = Depends(current_user)) -> UserOut:
    """Return the account attached to the supplied token."""
    return UserOut.model_validate(user)
