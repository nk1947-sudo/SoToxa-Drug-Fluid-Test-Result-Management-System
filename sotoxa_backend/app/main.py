from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from typing import Dict

from .db.mongodb import db
from .routers import drug_tests, auth
from .services.auth_service import AuthService
from .models.user import UserCreate, UserRole, UserInDB

app = FastAPI(
    title="Sotoxa Backend API",
    description="API for managing drug test results and processing",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(drug_tests.router)

@app.on_event("startup")
async def startup_db_client():
    await db.connect_to_database()
    
    # Create admin user if it doesn't exist
    if not await AuthService.get_user("admin"):
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com",
            password="admin123",  # Change this in production!
            role=UserRole.ADMIN
        )
        user_in_db = UserInDB(
            **admin_user.dict(exclude={'password'}),
            hashed_password=AuthService.get_password_hash(admin_user.password)
        )
        await db.db["users"].insert_one(user_in_db.dict(by_alias=True))

@app.on_event("shutdown")
async def shutdown_db_client():
    await db.close_database_connection()

@app.get("/", tags=["Health Check"])
async def root():
    """
    Root endpoint for API health check
    """
    return {
        "message": "Sotoxa Backend API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health", tags=["Health Check"])
async def health_check() -> Dict:
    """
    Health check endpoint to verify API and database status
    """
    try:
        # Check database connection
        await db.db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "api_version": "1.0.0"
    }

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """
    Custom Swagger UI documentation
    """
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Sotoxa Backend API Documentation",
        swagger_favicon_url="/favicon.ico"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    """
    Custom OpenAPI schema endpoint
    """
    return get_openapi(
        title="Sotoxa Backend API",
        version="1.0.0",
        description="API for managing drug test results and processing",
        routes=app.routes,
    )

# Error handlers
@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {
        "status_code": 500,
        "detail": "Internal server error",
        "path": request.url.path
    }



