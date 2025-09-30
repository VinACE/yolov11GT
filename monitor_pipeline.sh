#!/bin/bash
# Real-time pipeline monitoring script

clear
echo "🎥 Retail Analytics Pipeline Monitor"
echo "======================================"
echo ""

while true; do
    # Move cursor to top
    tput cup 3 0
    
    # Check if pipeline is running
    RUNNING=$(docker-compose -f /home/vinsent_120232/proj/yolov11/docker-compose.yolov11.yml exec yolov11 ps aux 2>/dev/null | grep run_pipeline | grep -v grep | wc -l)
    
    if [ "$RUNNING" -gt 0 ]; then
        echo "📹 Pipeline Status: 🟢 RUNNING                    "
    else
        echo "📹 Pipeline Status: 🔴 STOPPED                    "
    fi
    
    echo ""
    
    # Get current stats
    STATS=$(curl -s http://localhost:8000/stats 2>/dev/null)
    
    if [ -n "$STATS" ]; then
        ACTIVE=$(echo $STATS | python3 -c "import sys, json; print(json.load(sys.stdin)['active_visitors'])" 2>/dev/null)
        TOTAL=$(echo $STATS | python3 -c "import sys, json; print(json.load(sys.stdin)['total_today'])" 2>/dev/null)
        
        echo "📊 Live Statistics:"
        echo "   Active Visitors: $ACTIVE                       "
        echo "   Total Today:     $TOTAL                        "
    else
        echo "📊 API not responding...                          "
    fi
    
    echo ""
    echo "🌐 Access Dashboard: http://localhost:8501"
    echo ""
    echo "Press Ctrl+C to exit monitoring"
    echo "                                                      "
    
    sleep 2
done
