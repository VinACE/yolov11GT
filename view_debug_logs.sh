#!/bin/bash
# Quick viewer for debug logs

DEBUG_DIR="/app/outputs/debug"

echo "🔍 ReID Debug Log Viewer"
echo "========================"
echo ""

if [ ! -d "$DEBUG_DIR" ]; then
    echo "❌ Debug directory not found: $DEBUG_DIR"
    echo "   Run the pipeline first to generate logs."
    exit 1
fi

echo "Select option:"
echo "1) View summary"
echo "2) View recent ReID assignments (last 20)"
echo "3) View recent detections (last 20)"
echo "4) Run full ReID analysis"
echo "5) List annotated frames"
echo "6) Show all global IDs"
echo ""
read -p "Choice [1-6]: " choice

case $choice in
    1)
        echo "📊 Summary:"
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 cat $DEBUG_DIR/summary.json 2>/dev/null | python3 -m json.tool || echo "No summary yet"
        ;;
    2)
        echo "🔄 Recent ReID Assignments:"
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 tail -20 $DEBUG_DIR/reid_assignment_log.jsonl 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip():
        d = json.loads(line)
        type_icon = '🆕' if d['assignment_type'] == 'NEW_VISITOR' else '🔄'
        print(f\"{type_icon} [{d['camera_id']}] Frame {d['frame_number']:4d}: Local#{d['local_id']:3d} → {d['global_id']} (sim={d['similarity_score']:.3f})\")
" || echo "No ReID log yet"
        ;;
    3)
        echo "👁️  Recent Detections:"
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 tail -20 $DEBUG_DIR/detection_log.jsonl 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip():
        d = json.loads(line)
        print(f\"[{d['camera_id']}] Frame {d['frame_number']:4d}: {d['num_detections']} detections\")
        for det in d['detections']:
            print(f\"  - Local ID {det['local_id']} (conf={det['confidence']:.2f})\")
" || echo "No detection log yet"
        ;;
    4)
        echo "📈 Running full analysis..."
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 python3 /app/analyze_reid.py
        ;;
    5)
        echo "🖼️  Annotated Frames:"
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 ls -lh $DEBUG_DIR/annotated_frames/ 2>/dev/null | tail -20 || echo "No frames yet"
        ;;
    6)
        echo "🆔 All Global IDs:"
        docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 cat $DEBUG_DIR/summary.json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"Total unique global IDs: {len(data.get('known_global_ids', []))}\")
    print()
    for gid in data.get('known_global_ids', []):
        print(f\"  - {gid}\")
except:
    print('No summary available yet')
" || echo "No summary yet"
        ;;
    *)
        echo "Invalid choice"
        ;;
esac

echo ""
echo "📁 Debug files location: $DEBUG_DIR"
