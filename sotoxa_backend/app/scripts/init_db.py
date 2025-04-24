import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from ..core.config import get_settings

async def init_db():
    settings = get_settings()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    
    # Create indexes
    await db.drug_tests.create_index("person_id")
    await db.drug_tests.create_index("operator.id")
    await db.drug_tests.create_index("test_timestamp")
    await db.drug_tests.create_index("hash", unique=True)
    
    # Create indexes for users collection
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    
    print("Database initialization completed successfully!")
    
    # Test connection
    try:
        await client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(init_db())
