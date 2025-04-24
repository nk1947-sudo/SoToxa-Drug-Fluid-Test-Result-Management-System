from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from ..models.user import UserCreate, User, UserInDB, UserRole
from ..services.auth_service import AuthService
from ..core.config import get_settings
from ..db.mongodb import db
from typing import List

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await AuthService.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = AuthService.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/users", response_model=User)
async def create_user(
    user: UserCreate,
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN]))
):
    if await AuthService.get_user(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    user_in_db = UserInDB(
        **user.dict(exclude={'password'}),
        hashed_password=AuthService.get_password_hash(user.password)
    )
    
    result = await db.db["users"].insert_one(user_in_db.dict(by_alias=True))
    user_in_db.id = str(result.inserted_id)
    
    return User(**user_in_db.dict())

@router.get("/users", response_model=List[User])
async def list_users(
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN]))
):
    users = await db.db["users"].find().to_list(length=None)
    return [User(**user) for user in users]