# Real-Time Monitoring Commands

## Pipeline is Currently Running

The pipeline processes videos **without looping** and will automatically stop when all videos finish.

---

## Monitor Progress

### 1. Watch Live Pipeline Output:
```bash
docker exec yolov11-cpu tail -f /tmp/clean_run.log
```

### 2. Check Unique Visitor Count:
```bash
docker exec yolov11-mongo mongosh yolov11 --quiet --eval "db.visitors.countDocuments({})"
```

### 3. See Latest ReID Assignments:
```bash
docker exec yolov11-cpu tail -n 20 /tmp/clean_run.log | grep -E "(NEW|REID)"
```

### 4. Check Processing Speed:
```bash
docker exec yolov11-cpu bash -c "
  wc -l /app/outputs/debug/reid_assignment_log.jsonl
  echo 'ReID assignments logged'
"
```

### 5. View All Unique Visitors:
```bash
docker exec yolov11-mongo mongosh yolov11 --quiet --eval "
  db.visitors.find({}, {global_id: 1, first_seen_at: 1, last_seen_at: 1}).toArray()
"
```

###  6. ReID Performance Stats:
```bash
docker exec yolov11-cpu python3 << 'EOF'
import json
new = match = 0
sims = []
with open('/app/outputs/debug/reid_assignment_log.jsonl') as f:
    for line in f:
        ev = json.loads(line)
        if ev.get('assignment_type') == 'NEW_VISITOR':
            new += 1
        elif ev.get('assignment_type') == 'REID_MATCH':
            match += 1
            sim = ev.get('similarity_score', 0)
            if 0 < sim < 1.0:
                sims.append(sim)

print(f"NEW: {new}, MATCH: {match}, Match rate: {match/(new+match)*100:.1f}%")
if sims:
    print(f"Avg similarity: {sum(sims)/len(sims):.3f} (n={len(sims)})")
