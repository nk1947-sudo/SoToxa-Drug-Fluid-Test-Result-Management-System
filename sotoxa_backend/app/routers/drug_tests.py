from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, BackgroundTasks, Form, Query
from ..models.drug_test import DrugTest, Location, Operator, MetadataUpdate, TestSummary
from ..models.user import UserRole, UserInDB
from ..services.auth_service import AuthService
from ..services.upload_service import UploadService
from ..services.ocr_service import OCRService
from ..services.ocr_queue import OCRQueue
from ..services.export_service import ExportService
from ..db.mongodb import db
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from bson import ObjectId
import pymongo
from ..core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/api/drug-tests", tags=["drug-tests"])

@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=DrugTest)
async def upload_scan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    person_id: str = Form(...),
    operator_id: str = Form(...),
    operator_name: str = Form(...),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN, UserRole.OPERATOR]))
):
    """
    Upload a drug test scan (JPEG, PNG, or PDF) and process it with OCR.
    """
    if not person_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="person_id is required"
        )
        
    if not operator_id or not operator_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="operator_id and operator_name are required"
        )
    
    # Validate file
    try:
        if not await UploadService.validate_file(file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}. "
                       f"Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation error: {str(e)}"
        )
    
    try:
        # Save file
        file_url, file_hash = await UploadService.save_file(file)
        
        # Create drug test entry
        drug_test = DrugTest(
            scan_file_url=file_url,
            person_id=person_id,
            location=Location(latitude=lat, longitude=lon) if lat and lon else None,
            operator=Operator(id=operator_id, name=operator_name),
            test_timestamp=datetime.utcnow(),
            hash=file_hash
        )
        
        # Save to database
        result = await db.db["drug_tests"].insert_one(
            drug_test.model_dump(by_alias=True)
        )
        drug_test.id = str(result.inserted_id)
        
        # Queue OCR processing
        await OCRQueue.process_in_background(
            background_tasks,
            file_url,
            drug_test.id
        )
        
        return drug_test
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}"
        )

@router.get("/results/{test_id}", response_model=DrugTest)
async def get_test_result(
    test_id: str,
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER]))
):
    """Get detailed test result by ID"""
    result = await db.db["drug_tests"].find_one({"_id": ObjectId(test_id)})
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result

@router.get("/results", response_model=Dict)
async def list_test_results(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    operator: Optional[str] = None,
    person_id: Optional[str] = None,
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0, le=100),
    sort_by: str = Query("test_timestamp", regex="^(test_timestamp|person_id|operator.name)$"),
    sort_order: int = Query(-1, ge=-1, le=1),
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER]))
):
    """List test results with filtering, pagination and sorting"""
    # Build query
    query = {}
    if date_from or date_to:
        query["test_timestamp"] = {}
        if date_from:
            query["test_timestamp"]["$gte"] = date_from
        if date_to:
            query["test_timestamp"]["$lte"] = date_to
    if operator:
        query["operator.id"] = operator
    if person_id:
        query["person_id"] = person_id

    # Calculate skip value for pagination
    skip = (page - 1) * limit

    # Get total count for pagination
    total_count = await db.db["drug_tests"].count_documents(query)

    # Execute query with pagination and sorting
    cursor = db.db["drug_tests"].find(query)
    cursor.sort(sort_by, sort_order)
    cursor.skip(skip).limit(limit)
    
    results = await cursor.to_list(length=None)

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "results": results
    }

@router.get("/{test_id}/status", response_model=Dict[str, str])
async def get_processing_status(test_id: str):
    """Get the OCR processing status for a test"""
    result = await db.db["drug_tests"].find_one(
        {"_id": ObjectId(test_id)},
        {"processing_status": 1, "processing_error": 1}
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
        
    status_info = {
        "status": result["processing_status"]
    }
    
    if result.get("processing_error"):
        status_info["error"] = result["processing_error"]
        
    return status_info

@router.post("/{test_id}/metadata", response_model=DrugTest)
async def associate_metadata(
    test_id: str,
    metadata: MetadataUpdate,
    photo: Optional[UploadFile] = File(None)
):
    """
    Associate metadata with an existing drug test record.
    Optionally attach a photo of the person being tested.
    """
    # Verify test exists
    test = await db.db["drug_tests"].find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    update_data = {}

    # Process photo if provided
    if photo:
        try:
            if not await UploadService.validate_file(photo):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid photo file. Must be JPG or PNG."
                )
            photo_url, _ = await UploadService.save_file(photo)
            update_data["photo_url"] = photo_url
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process photo: {str(e)}"
            )

    # Update metadata fields
    if metadata.person_id:
        update_data["person_id"] = metadata.person_id

    if metadata.operator_id and metadata.operator_name:
        update_data["operator"] = {
            "id": metadata.operator_id,
            "name": metadata.operator_name
        }

    if metadata.test_timestamp:
        update_data["test_timestamp"] = metadata.test_timestamp

    if metadata.latitude is not None and metadata.longitude is not None:
        update_data["location"] = {
            "latitude": metadata.latitude,
            "longitude": metadata.longitude
        }

    # Update database
    try:
        result = await db.db["drug_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update test metadata"
            )

        # Return updated record
        updated_test = await db.db["drug_tests"].find_one(
            {"_id": ObjectId(test_id)}
        )
        return updated_test

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

# Dashboard endpoints
@router.get("/dashboard/summary", response_model=Dict[str, List[TestSummary]])
async def get_dashboard_summary(
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN, UserRole.OPERATOR]))
):
    """Get test count summary grouped by period"""
    now = datetime.utcnow()
    
    # Define date ranges based on period
    if period == "daily":
        start_date = now - timedelta(days=7)
        date_format = "%Y-%m-%d"
        group_format = {"$dateToString": {"format": "%Y-%m-%d", "date": "$test_timestamp"}}
    elif period == "weekly":
        start_date = now - timedelta(weeks=12)
        date_format = "%Y-W%V"
        group_format = {"$dateToString": {"format": "%Y-W%V", "date": "$test_timestamp"}}
    else:  # monthly
        start_date = now - timedelta(days=365)
        date_format = "%Y-%m"
        group_format = {"$dateToString": {"format": "%Y-%m", "date": "$test_timestamp"}}

    pipeline = [
        {"$match": {"test_timestamp": {"$gte": start_date}}},
        {
            "$group": {
                "_id": {
                    "date": group_format,
                    "status": "$processing_status"
                },
                "count": {"$sum": 1}
            }
        },
        {
            "$group": {
                "_id": "$_id.date",
                "total": {"$sum": "$count"},
                "completed": {
                    "$sum": {
                        "$cond": [{"$eq": ["$_id.status", "completed"]}, "$count", 0]
                    }
                },
                "failed": {
                    "$sum": {
                        "$cond": [{"$eq": ["$_id.status", "failed"]}, "$count", 0]
                    }
                }
            }
        },
        {"$sort": {"_id": 1}}
    ]

    results = await db.db["drug_tests"].aggregate(pipeline).to_list(length=None)
    
    # Add drug type statistics if available
    drug_stats = await get_drug_type_stats(start_date)

    return {
        "time_series": results,
        "drug_stats": drug_stats
    }

@router.get("/dashboard/export")
async def export_results(
    format: str = Query("csv", regex="^(csv|excel)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: UserInDB = Depends(AuthService.check_permissions([UserRole.ADMIN]))
):
    """Export test results in CSV or Excel format"""
    # Build query
    query = {}
    if date_from or date_to:
        query["test_timestamp"] = {}
        if date_from:
            query["test_timestamp"]["$gte"] = date_from
        if date_to:
            query["test_timestamp"]["$lte"] = date_to

    # Get results
    results = await db.db["drug_tests"].find(query).to_list(length=None)
    
    # Generate export file
    if format == "csv":
        content = await ExportService.generate_csv(results)
        media_type = "text/csv"
        filename = f"drug_tests_export_{datetime.now().strftime('%Y%m%d')}.csv"
    else:
        content = await ExportService.generate_excel(results)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"drug_tests_export_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

async def get_drug_type_stats(start_date: datetime) -> Dict:
    """Get statistics grouped by drug type"""
    pipeline = [
        {"$match": {
            "test_timestamp": {"$gte": start_date},
            "processing_status": "completed"
        }},
        {"$unwind": "$ocr_data"},
        {
            "$group": {
                "_id": "$ocr_data.drug_type",
                "total": {"$sum": 1},
                "positive": {
                    "$sum": {
                        "$cond": [{"$eq": ["$ocr_data.result", "positive"]}, 1, 0]
                    }
                }
            }
        }
    ]
    
    return await db.db["drug_tests"].aggregate(pipeline).to_list(length=None)


