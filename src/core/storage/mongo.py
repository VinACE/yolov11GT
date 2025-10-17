import os
from datetime import datetime
from typing import Optional, Dict, Any

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError


def get_mongo_client() -> MongoClient:
    uri = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
    return MongoClient(uri)


def get_mongo_db():
    client = get_mongo_client()
    db_name = os.environ.get("MONGO_DB", "yolov11")
    db = client[db_name]

    # Ensure basic indexes exist (idempotent, with error handling for unique constraint)
    try:
        db.visitors.create_index([("global_id", ASCENDING)], unique=True)
    except PyMongoError as e:
        # Index might already exist or there are duplicate values - continue anyway
        print(f"⚠️  Warning creating unique index on global_id: {e}")
    
    try:
        db.visitors.create_index([("last_seen_at", ASCENDING)])
        db.visit_events.create_index([("visitor_id", ASCENDING), ("camera_id", ASCENDING)])
        db.visit_events.create_index([("in_time", ASCENDING)])
        db.visit_events.create_index([("out_time", ASCENDING)])
        db.activity_events.create_index([("visitor_id", ASCENDING), ("zone", ASCENDING)])
        db.activity_events.create_index([("start_time", ASCENDING)])
    except PyMongoError as e:
        print(f"⚠️  Warning creating indexes: {e}")
    
    return db


def upsert_visitor(db, global_id: str, first_seen_at: datetime, last_seen_at: Optional[datetime] = None, gender: Optional[str] = None, face_crop_path: Optional[str] = None) -> Dict[str, Any]:
    last_seen = last_seen_at or first_seen_at
    update_doc = {
        "$setOnInsert": {"first_seen_at": first_seen_at},
        "$set": {"last_seen_at": last_seen}
    }
    # Add/refresh gender if provided (including 'unknown')
    if gender is not None:
        update_doc["$set"]["gender"] = gender
    # Add/refresh face crop path if provided
    if face_crop_path:
        update_doc["$set"]["face_crop_path"] = face_crop_path
    
    db.visitors.update_one(
        {"global_id": global_id},
        update_doc,
        upsert=True,
    )
    return db.visitors.find_one({"global_id": global_id})


def insert_visit_event(db, visitor_id: Any, camera_id: str, in_time: datetime, global_id: Optional[str] = None, gender: Optional[str] = None) -> Any:
    doc = {
        "visitor_id": visitor_id,
        "camera_id": camera_id,
        "in_time": in_time,
        "out_time": None,
    }
    if global_id is not None:
        doc["global_id"] = global_id
    if gender is not None:
        doc["gender"] = gender
    return db.visit_events.insert_one(doc).inserted_id


def close_open_visit(db, visitor_id: Any, out_time: datetime) -> None:
    db.visit_events.update_one(
        {"visitor_id": visitor_id, "out_time": None},
        {"$set": {"out_time": out_time}},
    )

