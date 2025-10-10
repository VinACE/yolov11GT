# Face Crops Visualization Feature

**Date**: October 8, 2025  
**Status**: ✅ **IMPLEMENTED**  
**Purpose**: Visual display of visitor face crops with gender information

---

## Overview

Face crops are now automatically saved when new visitors are detected and displayed in the Streamlit dashboard organized by gender.

---

## What Was Added

### 1. Face Crop Saving (Pipeline)

**Location**: `src/core/pipeline/multicam.py`

When a new visitor is detected:
1. Face crop is saved to `/app/outputs/debug/face_crops/{global_id}.jpg`
2. Path is stored in MongoDB `visitors` collection
3. Face is linked to visitor's global_id

**Example:**
```
outputs/debug/face_crops/
├── G1759894847_cam1_1.jpg
├── G1759894847_cam2_1.jpg
├── G1759894848_cam3_3.jpg
└── ...
```

### 2. MongoDB Schema Update

**Collection**: `visitors`

New fields added:
```javascript
{
    global_id: "G1759894847_cam1_1",
    first_seen_at: ISODate(...),
    last_seen_at: ISODate(...),
    gender: "male",                           // From gender classification
    face_crop_path: "outputs/debug/face_crops/G1759894847_cam1_1.jpg"  // NEW
}
```

### 3. Streamlit Dashboard Display

**New Section**: 🚻 Gender Distribution with Face Gallery

**Features**:
- Gender metrics (Males, Females, Unknown counts)
- **3 Tabs**:
  1. **👨 Males Tab** - Shows all male visitor faces (5 per row)
  2. **👩 Females Tab** - Shows all female visitor faces (5 per row)
  3. **👤 All Tab** - Shows all visitors (6 per row)

**Display**:
- Face crop images (80-100px width)
- Global ID caption (shortened)
- Gender icon
- Organized grid layout

---

## Streamlit UI Layout

```
🚻 Gender Distribution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨 Males: 6    👩 Females: 5    👤 Unknown: 0

👤 Visitor Face Gallery
┌─────────────┬─────────────┬─────────────┐
│  👨 Males   │  👩 Females │   👤 All    │
└─────────────┴─────────────┴─────────────┘

Males Tab:
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ IMG1 │ │ IMG2 │ │ IMG3 │ │ IMG4 │ │ IMG5 │
│ G175 │ │ G175 │ │ G175 │ │ G175 │ │ G175 │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

---

## Benefits

### 1. Visual Verification
- **See** who was counted (not just numbers)
- Verify gender classification accuracy
- Identify if same person counted multiple times
- Debug ReID matching visually

### 2. Gender Analytics
- Visual gender distribution
- Easy to spot classification errors
- Compare male vs female visitor crops
- Quality check for gender model

### 3. ReID Debugging
- If count is wrong (e.g., 9 vs 11), you can **see** which faces are similar
- Identify which 2 people are being merged
- Check if they're actually different genders
- Visual feedback for tuning

### 4. Production Monitoring
- Quick visual check of who visited
- Spot suspicious patterns
- Verify system is working correctly
- Better than just numbers!

---

## How It Works

### Pipeline Flow

```
1. Person detected by YOLO
2. Crop extracted from bbox
3. Gender classified (male/female/unknown)
4. ReID embedding generated
5. ⭐ CROP SAVED to outputs/debug/face_crops/{global_id}.jpg
6. ⭐ PATH STORED in MongoDB
7. Streamlit reads path and displays image
```

### Face Crop Storage

**Location**: `/app/outputs/debug/face_crops/`

**Filename Format**: `{global_id}.jpg`
- Example: `G1759894847_cam1_1.jpg`

**When Saved**: Only for new visitors (not on every match)

**Retention**: Persists until manually deleted

---

## Streamlit Display Features

### Tab 1: Males (👨)
- Shows up to 20 male visitors
- 5 faces per row
- 100px width per face
- Global ID caption

### Tab 2: Females (👩)
- Shows up to 20 female visitors
- 5 faces per row
- 100px width per face
- Global ID caption

### Tab 3: All (👤)
- Shows up to 30 visitors (all genders)
- 6 faces per row
- 80px width per face
- Gender icon + Global ID caption

---

## Example Use Cases

### Use Case 1: Verify Gender Classification

```
Look at Males tab:
  ✅ All faces look male? → Gender model working well
  ❌ Some faces look female? → Gender model needs tuning
```

### Use Case 2: Debug ReID Under-Counting (Your Case: 9 vs 11)

```
You see 9 unique faces but ground truth is 11
→ Look at face crops
→ Find 2 faces that look very similar
→ Those are the 2 people being merged!
→ Can verify if they're same gender or different
→ Helps decide if gender filtering will help
```

### Use Case 3: Debug ReID Over-Counting

```
You see 13 unique faces but ground truth is 11
→ Look at face crops
→ Find faces that are actually the same person
→ Those are being split into multiple IDs
→ Need higher quality crops (increase MIN_CROP_HEIGHT)
```

### Use Case 4: Production Monitoring

```
Quick visual check:
  - Are visitor crops clear and well-framed?
  - Is gender classification reasonable?
  - Any obvious duplicates?
  - System working as expected?
```

---

## File Locations

### Face Crops Directory

```
/app/outputs/debug/face_crops/
├── G1759894847_cam1_1.jpg
├── G1759894847_cam2_1.jpg
├── G1759894848_cam3_3.jpg
└── ...
```

Mounted to host at:
```
/home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/
```

### Accessing Face Crops

**From container**:
```bash
docker exec yolov11-cpu ls /app/outputs/debug/face_crops/
```

**From host**:
```bash
ls /home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/
```

**In Streamlit**:
- Navigate to http://localhost:8501
- Scroll to "🚻 Gender Distribution" section
- Click on tabs to see face galleries

---

## Clean Up Old Face Crops

Face crops accumulate over time. To clean up:

```bash
# Remove all face crops
rm -rf /home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/*

# Or keep only recent (last 100)
cd /home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/
ls -t | tail -n +101 | xargs rm -f
```

---

## Configuration

### Enable/Disable Face Crop Saving

Currently automatic for all new visitors. To disable, you would need to comment out the crop saving code in `multicam.py`.

### Crop Quality

Crop quality depends on `MIN_CROP_HEIGHT`:
- Higher value (e.g., 140) = Better quality but fewer crops
- Lower value (e.g., 100) = More crops but lower quality
- Current: 120 (balanced)

---

## Files Modified

1. ✅ `src/core/pipeline/multicam.py` - Save face crops on new visitor
2. ✅ `src/core/storage/mongo.py` - Store face_crop_path
3. ✅ `src/app/streamlit_app.py` - Display face gallery with tabs

---

## Testing

### Check if Face Crops Are Being Saved

```bash
# After running your test
ls -lh /home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/

# Count face crops
ls /home/vinsent_120232/proj/yolov11/outputs/debug/face_crops/ | wc -l
```

### View on Streamlit

1. Open http://localhost:8501
2. Run your test
3. Refresh Streamlit
4. Scroll to "🚻 Gender Distribution"
5. Click tabs to see face galleries organized by gender

### Check MongoDB

```bash
docker exec yolov11-cpu python3 -c "
import sys; sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
db = get_mongo_db()

for v in db.visitors.find().limit(3):
    gid = v.get('global_id')
    gender = v.get('gender', 'N/A')
    crop_path = v.get('face_crop_path', 'N/A')
    print(f'{gid}: {gender}, crop: {crop_path}')
"
```

---

## Summary

✅ **Face crops automatically saved** when new visitor detected  
✅ **Gender classified** for each face  
✅ **Streamlit displays** faces in organized tabs  
✅ **Visual debugging** tool for ReID accuracy  
✅ **Production monitoring** capability

**Next**: Run your test and open http://localhost:8501 to see the face gallery! 🎯


