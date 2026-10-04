from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URL") or "mongodb://localhost:27017", serverSelectionTimeoutMS=1500)
mongo_db = client["lms_db"]