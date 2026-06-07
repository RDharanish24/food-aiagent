import os
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = None
db = None

async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client.get_default_database()
    print("Connected to MongoDB")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Closed MongoDB connection")

# Helper collections getters
def get_sessions_collection():
    return db.sessions

def get_conversations_collection():
    return db.conversations

def get_order_logs_collection():
    return db.order_logs
