from motor.motor_asyncio import AsyncIOMotorClient
from ..core.config import get_settings

settings = get_settings()

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_database(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.client[settings.MONGODB_DB_NAME]
        
    async def close_database_connection(self):
        if self.client:
            self.client.close()

db = MongoDB()