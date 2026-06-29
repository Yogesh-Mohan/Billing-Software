"""
Diagnostic script to test Firebase Firestore read/write operations.
This will tell us exactly where the problem is.
"""
import os
import sys
import traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("FIREBASE READ/WRITE DIAGNOSTIC TEST")
print("="*60)

# Step 1: Check which database backend is being used
from app import db, USE_FIREBASE, USE_FILE_DB
print(f"\n[1] Database Backend:")
print(f"    USE_FIREBASE = {USE_FIREBASE}")
print(f"    USE_FILE_DB  = {USE_FILE_DB}")
print(f"    db type      = {type(db).__name__}")
print(f"    db module    = {type(db).__module__}")

# Step 2: Check items collection type
items_col = db.items
print(f"\n[2] Items Collection:")
print(f"    type          = {type(items_col).__name__}")
print(f"    module        = {type(items_col).__module__}")
print(f"    has _lock     = {hasattr(items_col, '_lock')}")
print(f"    has collection_ref = {hasattr(items_col, 'collection_ref')}")
if hasattr(items_col, 'file_path'):
    print(f"    file_path     = {items_col.file_path}")
if hasattr(items_col, 'collection_ref'):
    print(f"    collection_ref = {items_col.collection_ref}")

# Step 3: Read existing items from Firebase
print(f"\n[3] Reading items from database...")
try:
    existing_items = items_col._read()
    print(f"    Found {len(existing_items)} items:")
    for item in existing_items:
        print(f"      - {item.get('_id', '?')}: code={item.get('item_code', '?')}, name={item.get('item_name', '?')}")
except Exception as e:
    print(f"    ERROR reading: {e}")
    traceback.print_exc()

# Step 4: Try to write a test document
print(f"\n[4] Writing test item to database...")
from datetime import datetime
test_doc = {
    "item_code": "TEST-DIAG-001",
    "item_name": "Diagnostic Test Item",
    "description": "Auto test - can be deleted",
    "quantity": "",
    "price": 1.0,
    "tax": "",
    "manage_stock": False,
    "current_qty": 0,
    "ideal_qty": 0,
    "warning_qty": 0,
    "supplier": "Test",
    "note": "diagnostic",
    "created_at": datetime.utcnow()
}

try:
    result = items_col.insert_one(test_doc)
    print(f"    SUCCESS! Inserted with _id = {result.inserted_id}")
except Exception as e:
    print(f"    ERROR writing: {e}")
    traceback.print_exc()

# Step 5: Read back to confirm
print(f"\n[5] Reading back to confirm write...")
try:
    found = items_col.find_one({"item_code": "TEST-DIAG-001"})
    if found:
        print(f"    SUCCESS! Found test item: _id={found['_id']}, name={found.get('item_name')}")
    else:
        print(f"    FAILED! Test item NOT found after write!")
        # Check if it's in local file DB instead
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'red_studio_billing', 'items.json')
        if os.path.exists(local_path):
            import json
            with open(local_path, 'r') as f:
                local_data = json.load(f)
            local_test = [d for d in local_data if d.get('item_code') == 'TEST-DIAG-001']
            if local_test:
                print(f"    ** FOUND IN LOCAL FILE DB INSTEAD! **")
                print(f"    ** This means data is going to local files, NOT Firebase **")
except Exception as e:
    print(f"    ERROR reading back: {e}")
    traceback.print_exc()

# Step 6: Cleanup - delete test item
print(f"\n[6] Cleaning up test item...")
try:
    items_col.delete_one({"item_code": "TEST-DIAG-001"})
    print(f"    Deleted test item.")
except Exception as e:
    print(f"    ERROR deleting: {e}")

# Step 7: Final count
print(f"\n[7] Final item count: {items_col.count_documents({})}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
