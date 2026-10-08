from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(
    os.getenv("MONGO_URL") or "mongodb://localhost:27017",
    serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "750")),
    connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "750")),
    socketTimeoutMS=int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "2000")),
    maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "20")),
    minPoolSize=int(os.getenv("MONGO_MIN_POOL_SIZE", "1")),
)
mongo_db = client[os.getenv("MONGODB_DATABASE", "lms_db")]