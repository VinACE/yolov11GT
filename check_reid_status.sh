#!/bin/bash
# Comprehensive ReID status checker

echo "=========================================="
echo "ReID System Status Checker"
echo "=========================================="
echo ""

# Check which embedder is configured
echo "1️⃣  Configuration:"
echo "-----------------------------------------"
docker exec yolov11-cpu printenv | grep -E "USE_HYBRID_REID|FASTREID_ENABLED|REID_SIM_THRESHOLD"
echo ""

# Check what's actually running
echo "2️⃣  Running Processes:"
echo "-----------------------------------------"
docker exec yolov11-cpu ps aux | grep -E "run_pipeline|uvicorn|streamlit" | grep -v grep
echo ""

# Check database status
echo "3️⃣  Database Status:"
echo "-----------------------------------------"
docker exec yolov11-cpu python3 << 'EOF'
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
from collections import Counter

db = get_mongo_db()
visitors = list(db.visitors.find())

print(f"Total visitors: {len(visitors)}")

# Check for duplicates
gid_counts = Counter(v.get('global_id') for v in visitors)
duplicates = sum(1 for count in gid_counts.values() if count > 1)

if duplicates > 0:
    print(f"❌ {duplicates} duplicate global IDs found!")
else:
    print(f"✅ No duplicate global IDs")

# Check gender distribution
males = sum(1 for v in visitors if v.get('gender') == 'male')
females = sum(1 for v in visitors if v.get('gender') == 'female')
unknown = sum(1 for v in visitors if v.get('gender') == 'unknown')

print(f"Males: {males}, Females: {females}, Unknown: {unknown}")

# Check for cross-gender
from collections import defaultdict
by_gid = defaultdict(list)
for v in visitors:
    gid = v.get('global_id')
    gender = v.get('gender', 'unknown')
    by_gid[gid].append(gender)

cross_gender = 0
for gid, genders in by_gid.items():
    known = set(g for g in genders if g != 'unknown')
    if len(known) > 1:
        cross_gender += 1
        print(f"❌ Cross-gender: {gid} → {genders}")

if cross_gender == 0:
    print("✅ No cross-gender matches")
EOF
echo ""

# Check recent similarity scores
echo "4️⃣  Recent ReID Similarity Scores:"
echo "-----------------------------------------"
docker exec yolov11-cpu bash -c "
if [ -f /app/outputs/debug/reid_assignment_log.jsonl ]; then
    tail -20 /app/outputs/debug/reid_assignment_log.jsonl | python3 -c \"
import sys, json
sims = []
for line in sys.stdin:
    try:
        d = json.loads(line)
        sim = d.get('similarity_score', 0)
        if sim > 0:
            sims.append(sim)
    except: pass

if sims:
    print(f'Total matches: {len(sims)}')
    print(f'Avg similarity: {sum(sims)/len(sims):.3f}')
    print(f'Min similarity: {min(sims):.3f}')
    print(f'Max similarity: {max(sims):.3f}')
    if all(s >= 0.99 for s in sims):
        print('❌ WARNING: All similarities are 1.0 - embeddings may be identical!')
    else:
        print('✅ Similarities are varied (embeddings working)')
else:
    print('No similarity data')
\"
else
    echo 'No reid_assignment_log.jsonl file'
fi
"
echo ""

# Test embedder directly
echo "5️⃣  Testing Embedder Quality:"
echo "-----------------------------------------"
docker exec yolov11-cpu python3 << 'EOF'
import sys
sys.path.insert(0, '/app/src')
import numpy as np

# Check if Hybrid is being used
import os
hybrid_enabled = os.environ.get('USE_HYBRID_REID', '0') == '1'
print(f"USE_HYBRID_REID environment: {hybrid_enabled}")

# Test import
try:
    from core.reid.facenet_embedder import HybridEmbedder
    embedder = HybridEmbedder()
    
    print(f"Embedder type: {type(embedder).__name__}")
    print(f"Face enabled: {embedder.face_enabled}")
    print(f"Dimension: {embedder.dim}")
    
    # Quick embedding test
    test1 = np.random.randint(0, 100, (256, 128, 3), dtype=np.uint8)
    test2 = np.random.randint(150, 255, (256, 128, 3), dtype=np.uint8)
    
    emb1 = embedder.embed(test1)
    emb2 = embedder.embed(test2)
    
    sim = np.dot(emb1, emb2)
    print(f"Test similarity: {sim:.4f}")
    
    if sim > 0.99:
        print("❌ WARNING: Test embeddings too similar!")
    else:
        print("✅ Embeddings look different")
        
except Exception as e:
    print(f"❌ Error loading embedder: {e}")
EOF
echo ""

echo "=========================================="
echo "Status Check Complete"
echo "=========================================="


