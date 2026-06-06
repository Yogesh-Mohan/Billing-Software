"""
Seed the file-based database with the default admin user and initial data.
Run this once after setting up the file-based DB for the first time.
"""
import os
import sys
import json
import bcrypt
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from file_db import FileClient

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
client = FileClient(data_dir)
db = client['red_studio_billing']

# Check if admin user already exists
existing_user = db.users.find_one({"username": "admin"})
if existing_user:
    print("[SKIP] Admin user already exists.")
else:
    hashed_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
    db.users.insert_one({
        "username": "admin",
        "password": hashed_pw.decode('utf-8'),
        "created_at": datetime.utcnow().isoformat()
    })
    print("[OK] Admin user created (username: admin, password: admin123)")

# Import exported data if available
for col_name in ['customers', 'items', 'invoices', 'settings']:
    export_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'export_{col_name}.json')
    if os.path.exists(export_file):
        existing_count = db[col_name].count_documents({})
        if existing_count > 0:
            print(f"[SKIP] '{col_name}' already has {existing_count} documents.")
            continue
        
        with open(export_file, 'r', encoding='utf-8') as f:
            try:
                docs = json.load(f)
            except json.JSONDecodeError:
                print(f"[ERROR] Could not parse {export_file}")
                continue
        
        imported = 0
        for doc in docs:
            # Convert MongoDB $oid format to string
            if '_id' in doc:
                if isinstance(doc['_id'], dict) and '$oid' in doc['_id']:
                    doc['_id'] = doc['_id']['$oid']
                else:
                    doc['_id'] = str(doc['_id'])
            
            # Convert MongoDB $date format
            for key, val in list(doc.items()):
                if isinstance(val, dict) and '$date' in val:
                    doc[key] = val['$date']
                elif isinstance(val, dict) and '$binary' in val:
                    # Handle binary password fields
                    import base64
                    doc[key] = base64.b64decode(val['$binary']['base64']).decode('utf-8', errors='replace')
            
            db[col_name].insert_one(doc)
            imported += 1
        
        print(f"[OK] Imported {imported} documents into '{col_name}'")
    else:
        print(f"[INFO] No export file found for '{col_name}' (expected: export_{col_name}.json)")

print("\n[DONE] Database seed complete!")
print(f"[INFO] Data stored at: {data_dir}")
print("[INFO] Login with: username=admin, password=admin123")
