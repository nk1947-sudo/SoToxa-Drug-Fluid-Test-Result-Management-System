from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field, validator
from fastapi import UploadFile
from bson import ObjectId

class Location(BaseModel):
    latitude: float
    longitude: float

class Operator(BaseModel):
    id: str
    name: str

class DrugTest(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    scan_file_url: str
    ocr_text: Optional[str] = ""
    ocr_data: Dict[str, str] = Field(default_factory=dict)
    person_id: str
    photo_url: Optional[str] = None
    location: Optional[Location] = None
    operator: Operator
    test_timestamp: datetime
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    hash: str
    ocr_confidence: float = 0.0
    processing_status: str = "pending"  # pending, completed, failed
    processing_error: Optional[str] = None

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
        arbitrary_types_allowed = True

class MetadataUpdate(BaseModel):
    person_id: Optional[str] = None
    operator_id: Optional[str] = None
    operator_name: Optional[str] = None
    test_timestamp: Optional[datetime] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @validator('test_timestamp')
    def validate_timestamp(cls, v):
        if v and v > datetime.utcnow():
            raise ValueError("Test timestamp cannot be in the future")
        return v

class TestSummary(BaseModel):
    date: str
    total: int
    completed: int
    failed: int
    
    class Config:
        json_encoders = {ObjectId: str}



