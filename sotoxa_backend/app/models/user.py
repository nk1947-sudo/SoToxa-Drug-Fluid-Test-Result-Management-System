from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum
from bson import ObjectId

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: UserRole = UserRole.VIEWER
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    hashed_password: str

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

class User(UserBase):
    id: str

class UserLogin(BaseModel):
    username: str
    password: str