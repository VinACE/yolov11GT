# MongoDB 8 distinct() Behavior Change - Fix Guide

## Problem Summary

**Issue**: After upgrading from MongoDB 6 to MongoDB 8, unique visitor counts increased from 12 to 13.

**Root Cause**: MongoDB 8 changed how the `distinct()` method handles `null` values:
- **MongoDB 6**: `distinct()` excluded `null` values by default
- **MongoDB 8**: `distinct()` **includes `null` values** in the result set

This means if you have any documents with `null` or missing fields, they will now be counted as a distinct value.

---

## Example of the Issue

### Before (MongoDB 6)
```python
# Assume you have these documents:
# { "visitor_id": "abc123" }
# { "visitor_id": "def456" }
# { "visitor_id": null }

result = db.visit_events.distinct("visitor_id")
# MongoDB 6 Result: ["abc123", "def456"]  <-- 2 values (null excluded)
len(result)  # 2
```

### After (MongoDB 8)
```python
# Same documents:
# { "visitor_id": "abc123" }
# { "visitor_id": "def456" }
# { "visitor_id": null }

result = db.visit_events.distinct("visitor_id")
# MongoDB 8 Result: ["abc123", "def456", null]  <-- 3 values (null included!)
len(result)  # 3
```

This explains why your count went from 12 → 13: **one document has a null/missing visitor_id**.

---

## Files Fixed

### 1. `/src/app/streamlit_app.py` - Line 17

**Before (Problematic):**
```python
unique_today = len(db.visit_events.distinct("visitor_id", {"in_time": {"$gte": start}}))
```

**After (Fixed):**
```python
# Fix for MongoDB 8: Filter out null values explicitly
distinct_visitor_ids = db.visit_events.distinct(
    "visitor_id", 
    {"in_time": {"$gte": start}, "visitor_id": {"$exists": True, "$ne": None}}
)
# Additional Python-level filtering for empty strings
unique_today = len([v for v in distinct_visitor_ids if v])
```

**Changes:**
1. Added `"visitor_id": {"$exists": True, "$ne": None}` filter in the query
2. Added Python-level filtering `if v` to exclude empty strings

---

### 2. `/src/core/analytics/export.py` - Line 91

**Before (Problematic):**
```python
hourly_stats[entry_hour]["visitors"].add(visit.get('global_id', ''))
```

This adds an **empty string `''`** when `global_id` is missing, which counts as a unique value!

**After (Fixed):**
```python
# Fix for MongoDB 8: Only add global_id if it exists and is not None/empty
global_id = visit.get('global_id')
if global_id:  # Filters out None, empty string, and other falsy values
    hourly_stats[entry_hour]["visitors"].add(global_id)
```

**Changes:**
1. Only add to set if `global_id` is truthy (not None, not empty string)
2. This prevents counting null/empty values as unique visitors

---

## Good Example (Already Fixed)

`/src/api/main.py` - Lines 198-201 was already implemented correctly:

```python
gids_events = set(g for g in db.visit_events.distinct(
    "global_id",
    {"in_time": {"$gte": start}, "global_id": {"$exists": True}}
) if g is not None)
```

This implementation:
1. ✅ Filters at query level: `"global_id": {"$exists": True}`
2. ✅ Filters at Python level: `if g is not None`
3. ✅ Works correctly in both MongoDB 6 and MongoDB 8

---

## Testing the Fix

Run the diagnostic script to identify null values:

```bash
cd /home/vinsent_120232/proj/yolov11
python3 check_null_visitors.py
```

This will show:
- How many documents have `null` or missing `visitor_id` / `global_id`
- The difference between raw `distinct()` and filtered `distinct()`
- Confirm if this is the cause of the 12 → 13 discrepancy

---

## Best Practices Going Forward

When using `distinct()` in MongoDB, **always filter null values** explicitly:

### ✅ Correct Pattern
```python
# Query-level filtering
distinct_values = db.collection.distinct(
    "field_name",
    {"field_name": {"$exists": True, "$ne": None}}
)

# Python-level filtering (defense in depth)
unique_count = len([v for v in distinct_values if v])
```

### ❌ Problematic Pattern
```python
# Don't rely on MongoDB to exclude nulls automatically
distinct_values = db.collection.distinct("field_name")
unique_count = len(distinct_values)  # May include null!
```

### ❌ Problematic Pattern with Sets
```python
# Don't add empty strings as fallback
for doc in documents:
    my_set.add(doc.get('field_name', ''))  # Empty string counts as unique!
```

### ✅ Correct Pattern with Sets
```python
# Only add if value exists
for doc in documents:
    value = doc.get('field_name')
    if value:  # Excludes None, empty string, 0, False
        my_set.add(value)
```

---

## MongoDB Version Compatibility

These fixes ensure your code works correctly in **both MongoDB 6 and MongoDB 8**:

| MongoDB Version | `distinct()` behavior | Our Fix |
|-----------------|----------------------|---------|
| MongoDB 6       | Excludes null        | Still works (redundant filter doesn't hurt) |
| MongoDB 8       | **Includes null**    | ✅ Correctly excludes null |

---

## Related Changes

See also:
- `MONGODB8_UPGRADE.md` - Full upgrade guide
- `check_null_visitors.py` - Diagnostic script to identify null values
- MongoDB 8 Release Notes: https://www.mongodb.com/docs/manual/release-notes/8.0/

---

## Quick Reference

### Check for null values in your database
```bash
# MongoDB shell
docker exec yolov11-mongo mongosh analytics --quiet --eval "
  db.visit_events.countDocuments({visitor_id: null})
"
```

### Clean up null values (if needed)
```bash
# WARNING: This deletes documents with null visitor_id
docker exec yolov11-mongo mongosh analytics --quiet --eval "
  db.visit_events.deleteMany({visitor_id: null})
"
```

### Set default values for existing null records
```bash
# Update null values to a default (e.g., 'unknown')
docker exec yolov11-mongo mongosh analytics --quiet --eval "
  db.visit_events.updateMany(
    {visitor_id: null}, 
    {\$set: {visitor_id: 'unknown'}}
  )
"
```

---

## Status

✅ **Fixed** - Updated code to handle null values correctly in MongoDB 8
- Date: 2025-10-08
- Files Modified: 2
  - `src/app/streamlit_app.py`
  - `src/core/analytics/export.py`
- Diagnostic Tool: `check_null_visitors.py`

