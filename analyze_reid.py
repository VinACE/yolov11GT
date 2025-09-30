#!/usr/bin/env python3
"""
Analyze ReID assignments and verify ID consistency
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def analyze_reid_logs(debug_dir="/app/outputs/debug"):
    debug_path = Path(debug_dir)
    reid_log = debug_path / "reid_assignment_log.jsonl"
    
    if not reid_log.exists():
        print(f"❌ ReID log not found at: {reid_log}")
        print("   Make sure the pipeline has run with debug logging enabled.")
        return
    
    print("📊 ReID Assignment Analysis")
    print("=" * 80)
    print()
    
    # Parse log entries
    assignments = []
    with open(reid_log, "r") as f:
        for line in f:
            if line.strip():
                assignments.append(json.loads(line))
    
    print(f"Total ReID operations: {len(assignments)}")
    print()
    
    # Group by assignment type
    new_visitors = [a for a in assignments if a["assignment_type"] == "NEW_VISITOR"]
    reid_matches = [a for a in assignments if a["assignment_type"] == "REID_MATCH"]
    
    print(f"🆕 New Visitors Created: {len(new_visitors)}")
    print(f"🔄 ReID Matches Found:   {len(reid_matches)}")
    print()
    
    # Analyze global ID assignments
    global_id_timeline = defaultdict(list)
    for a in assignments:
        global_id_timeline[a["global_id"]].append(a)
    
    print(f"📋 Unique Global IDs: {len(global_id_timeline)}")
    print()
    
    # Detailed breakdown per global ID
    print("=" * 80)
    print("GLOBAL ID ASSIGNMENT HISTORY:")
    print("=" * 80)
    print()
    
    for gid in sorted(global_id_timeline.keys()):
        events = global_id_timeline[gid]
        first_event = events[0]
        
        print(f"Global ID: {gid}")
        print(f"  Created: {first_event['timestamp']}")
        print(f"  Camera:  {first_event['camera_id']}")
        print(f"  Local ID at creation: {first_event['local_id']}")
        print(f"  Total assignments: {len(events)}")
        
        # Show camera transitions
        cameras_seen = {}
        for e in events:
            cam = e["camera_id"]
            if cam not in cameras_seen:
                cameras_seen[cam] = {"first": e["frame_number"], "count": 0}
            cameras_seen[cam]["count"] += 1
        
        print(f"  Cameras seen: {list(cameras_seen.keys())}")
        for cam, info in cameras_seen.items():
            print(f"    - {cam}: {info['count']} frames (first seen at frame {info['first']})")
        
        # Show ReID match quality
        reid_similarities = [e["similarity_score"] for e in events if e["assignment_type"] == "REID_MATCH"]
        if reid_similarities:
            avg_sim = sum(reid_similarities) / len(reid_similarities)
            min_sim = min(reid_similarities)
            max_sim = max(reid_similarities)
            print(f"  ReID similarity: avg={avg_sim:.3f}, min={min_sim:.3f}, max={max_sim:.3f}")
        
        print()
    
    # Cross-camera tracking analysis
    print("=" * 80)
    print("CROSS-CAMERA TRACKING:")
    print("=" * 80)
    print()
    
    cross_camera_ids = [gid for gid, events in global_id_timeline.items() 
                        if len(set(e["camera_id"] for e in events)) > 1]
    
    if cross_camera_ids:
        print(f"✅ {len(cross_camera_ids)} visitors tracked across multiple cameras:")
        for gid in cross_camera_ids:
            events = global_id_timeline[gid]
            cameras = [e["camera_id"] for e in events]
            camera_path = " → ".join(dict.fromkeys(cameras))  # Remove consecutive duplicates
            print(f"  {gid}: {camera_path}")
    else:
        print("⚠️  No cross-camera tracking detected yet.")
        print("   This may mean:")
        print("   - Videos don't show the same people")
        print("   - ReID threshold is too strict (currently 0.7)")
        print("   - ReID embeddings need improvement")
    
    print()
    
    # Potential issues
    print("=" * 80)
    print("POTENTIAL ISSUES:")
    print("=" * 80)
    print()
    
    # Check for duplicate assignments at same time
    same_frame_dups = defaultdict(list)
    for a in assignments:
        key = (a["camera_id"], a["frame_number"], a["local_id"])
        same_frame_dups[key].append(a["global_id"])
    
    duplicates = {k: v for k, v in same_frame_dups.items() if len(set(v)) > 1}
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} cases where same local_id got different global_ids:")
        for (cam, frame, local_id), gids in list(duplicates.items())[:5]:  # Show first 5
            print(f"  Camera {cam}, Frame {frame}, Local ID {local_id} → {set(gids)}")
    else:
        print("✅ No duplicate global ID assignments detected")
    
    print()
    
    # Summary recommendation
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    print()
    
    if len(cross_camera_ids) > 0:
        print("✅ Cross-camera ReID is working!")
    else:
        print("💡 To improve cross-camera tracking:")
        print("   1. Lower ReID similarity threshold (currently 0.7)")
        print("   2. Use a trained ReID model instead of random embeddings")
        print("   3. Ensure videos show similar people/clothing")
    
    print()
    print(f"📁 Full logs available at: {debug_dir}")
    print(f"   - Detection log:  {debug_path / 'detection_log.jsonl'}")
    print(f"   - ReID log:       {reid_log}")
    print(f"   - Summary:        {debug_path / 'summary.json'}")
    print(f"   - Frames:         {debug_path / 'annotated_frames/'}")


if __name__ == "__main__":
    debug_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/outputs/debug"
    analyze_reid_logs(debug_dir)
