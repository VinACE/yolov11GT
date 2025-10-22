#!/usr/bin/env python3
"""Populate MongoDB with test data for demonstration"""

import sys
sys.path.insert(0, '/app/src')

from core.storage.mongo import get_mongo_db, upsert_visitor, insert_visit_event
from datetime import datetime, timedelta
import random

def main():
    db = get_mongo_db()
    
    # Clear existing data
    db.visitors.delete_many({})
    db.visit_events.delete_many({})
    print("🧹 Cleared existing data")
    
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    
    # Create sample visitors across different hours and cameras
    cameras = ["cam1", "cam2", "cam3"]
    hours_data = [
        (8, 5),   # 8am: 5 visitors
        (9, 12),  # 9am: 12 visitors
        (10, 8),
        (11, 10),
        (12, 15), # 12pm: 15 visitors (busiest)
        (13, 11),
        (14, 9),
        (15, 7),
        (16, 4),
    ]
    
    visitor_id = 1
    for hour, count in hours_data:
        for i in range(count):
            global_id = f"PERSON_{visitor_id:03d}"
            camera_id = random.choice(cameras)
            
            # Entry time
            entry_time = today_start + timedelta(hours=hour, minutes=random.randint(0, 55))
            
            # Dwell time between 5-45 minutes
            dwell_minutes = random.randint(5, 45)
            exit_time = entry_time + timedelta(minutes=dwell_minutes)
            
            # Create visitor and visit event
            visitor_doc = upsert_visitor(db, global_id, entry_time, exit_time)
            event_id = insert_visit_event(db, visitor_doc['_id'], camera_id, entry_time, global_id=global_id)
            
            # Close the visit
            db.visit_events.update_one({"_id": event_id}, {"$set": {"out_time": exit_time}})
            
            visitor_id += 1
    
    # Add some active visitors (no exit time)
    for i in range(3):
        global_id = f"PERSON_{visitor_id:03d}"
        camera_id = random.choice(cameras)
        entry_time = now - timedelta(minutes=random.randint(5, 15))
        
        visitor_doc = upsert_visitor(db, global_id, entry_time, now)
        insert_visit_event(db, visitor_doc['_id'], camera_id, entry_time, global_id=global_id)
        visitor_id += 1
    
    print(f"✅ Created {visitor_id-1} test visitors")
    print(f"   📊 {len(hours_data)} hourly buckets")
    print(f"   👤 3 active visitors currently inside")
    print(f"   📹 Across {len(cameras)} cameras")
    print(f"\n📈 Database stats:")
    print(f"   Visitors: {db.visitors.count_documents({})}")
    print(f"   Visit events: {db.visit_events.count_documents({})}")
    print(f"   Active visits: {db.visit_events.count_documents({'out_time': None})}")

if __name__ == "__main__":
    main()

