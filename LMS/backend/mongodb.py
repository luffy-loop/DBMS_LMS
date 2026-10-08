from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

environment = os.getenv("ENVIRONMENT", "development").lower()
mongo_url = os.getenv("MONGO_URL")
if not mongo_url:
    if environment == "production":
        raise RuntimeError("MONGO_URL must be configured in production")
    mongo_url = "mongodb://localhost:27017"

client = MongoClient(
    mongo_url,
    serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "750")),
    connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "750")),
    socketTimeoutMS=int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "2000")),
    maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "20")),
    minPoolSize=int(os.getenv("MONGO_MIN_POOL_SIZE", "1")),
)
mongo_db = client[os.getenv("MONGODB_DATABASE", "lms_db")]