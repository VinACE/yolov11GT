#!/bin/bash
# Show current system status - easy to read

echo "=========================================="
echo "📊 Current System Status"
echo "=========================================="
echo ""

# 1. Services running
echo "1️⃣  Services Running:"
echo "-----------------------------------------"
docker exec yolov11-cpu ps aux | grep -E "python.*run_pipeline|streamlit|uvicorn" | grep -v grep | awk '{print "✅", $11, $12, $13, $14, $15}'
echo ""

# 2. Configuration
echo "2️⃣  ReID Configuration:"
echo "-----------------------------------------"
docker exec yolov11-cpu printenv | grep -E "USE_HYBRID_REID|REID_SIM_THRESHOLD|GENDER_CLASSIFICATION"
echo ""

# 3. Database status
echo "3️⃣  Database Status:"
echo "-----------------------------------------"
docker exec yolov11-mongo mongosh --quiet yolov11 --eval "
var visitors = db.visitors.countDocuments({});
var events = db.visit_events.countDocuments({});
print('Visitors: ' + visitors);
print('Events: ' + events);

if (visitors > 0) {
  print('');
  print('Latest 5 visitors:');
  db.visitors.find().sort({first_seen_at: -1}).limit(5).forEach(doc => {
    print('  ' + doc.global_id + ': ' + (doc.gender || 'unknown'));
  });
}
"
echo ""

# 4. Check which embedder is loaded
echo "4️⃣  Checking ReID Embedder:"
echo "-----------------------------------------"
docker exec yolov11-cpu python3 << 'EOF'
import sys
sys.path.insert(0, '/app/src')

try:
    from core.reid.facenet_embedder import HybridEmbedder
    import os
    
    hybrid_enabled = os.environ.get('USE_HYBRID_REID', '0') == '1'
    print(f"USE_HYBRID_REID env: {hybrid_enabled}")
    
    embedder = HybridEmbedder()
    print(f"Embedder type: {type(embedder).__name__}")
    print(f"Face enabled: {embedder.face_enabled}")
    
    if embedder.face_enabled:
        print("✅ Hybrid is working (FaceNet + OSNet)")
    else:
        print("⚠️  Hybrid fallback (OSNet only, FaceNet failed)")
        
except Exception as e:
    print(f"❌ Error: {e}")
EOF
echo ""

# 5. Check for duplicate IDs
echo "5️⃣  Checking for Duplicate Global IDs:"
echo "-----------------------------------------"
docker exec yolov11-mongo mongosh --quiet yolov11 --eval "
var dups = db.visitors.aggregate([
  { \$group: { _id: '\$global_id', count: { \$sum: 1 }, genders: { \$addToSet: '\$gender' } } },
  { \$match: { count: { \$gt: 1 } } }
]).toArray();

if (dups.length > 0) {
  print('❌ Found ' + dups.length + ' duplicate global IDs:');
  dups.forEach(d => {
    print('  ' + d._id + ': ' + d.count + ' times, genders=' + d.genders.join(','));
  });
} else {
  var total = db.visitors.countDocuments({});
  if (total > 0) {
    print('✅ No duplicate global IDs (each visitor is unique)');
  } else {
    print('⏳ No visitors yet');
  }
}
"
echo ""

echo "=========================================="
echo "Streamlit Dashboard: http://localhost:8501"
echo "API Docs: http://localhost:8000/docs"
echo "=========================================="


