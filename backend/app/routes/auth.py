from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.schemas import SignupRequest, LoginRequest, AuthResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.signup(db, req.email, req.password)
    return user


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    token, expires_in = await auth_service.login(db, req.email, req.password)
    return AuthResponse(access_token=token, expires_in=expires_in)
