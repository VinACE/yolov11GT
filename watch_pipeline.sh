#!/bin/bash
# Watch pipeline in real-time - shows what's happening NOW

echo "=========================================="
echo "🔍 Real-Time Pipeline Monitor"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop watching"
echo ""

# Function to show status
show_status() {
    clear
    echo "=========================================="
    echo "📊 Pipeline Status (refreshing every 5s)"
    echo "=========================================="
    date
    echo ""
    
    # Services
    echo "🟢 Services:"
    docker exec yolov11-cpu ps aux | grep -E "run_pipeline|streamlit|uvicorn" | grep -v grep | wc -l | xargs echo "  Running processes:"
    
    # Database
    echo ""
    echo "💾 Database:"
    VISITORS=$(docker exec yolov11-mongo mongosh --quiet yolov11 --eval "db.visitors.countDocuments({})" 2>/dev/null || echo "0")
    echo "  Visitors: $VISITORS"
    
    # Latest frames
    echo ""
    echo "📸 Latest Processed Frames:"
    docker exec yolov11-cpu ls -lt /app/outputs/debug/annotated_frames/*.jpg 2>/dev/null | head -3 | awk '{print "  " $9, "(" $6, $7, $8 ")"}'
    
    # Latest visitors if any
    if [ "$VISITORS" != "0" ] && [ "$VISITORS" -gt 0 ]; then
        echo ""
        echo "👥 Latest 5 Visitors:"
        docker exec yolov11-mongo mongosh --quiet yolov11 --eval "
        db.visitors.find().sort({first_seen_at: -1}).limit(5).forEach(doc => {
            print('  ' + doc.global_id + ': ' + (doc.gender || 'unknown'));
        });" 2>/dev/null
    fi
    
    # ReID logs if any
    if docker exec yolov11-cpu test -f /app/outputs/debug/reid_assignment_log.jsonl 2>/dev/null; then
        REID_LINES=$(docker exec yolov11-cpu wc -l /app/outputs/debug/reid_assignment_log.jsonl 2>/dev/null | awk '{print $1}')
        echo ""
        echo "📋 ReID Assignments: $REID_LINES total"
    fi
    
    echo ""
    echo "=========================================="
    echo "Streamlit: http://localhost:8501"
    echo "Press Ctrl+C to stop"
    echo "=========================================="
}

# Watch loop
while true; do
    show_status
    sleep 5
done


