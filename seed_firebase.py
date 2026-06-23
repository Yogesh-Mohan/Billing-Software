"""
Seed the Firebase Firestore database with exported data from JSON files.
This will recursively clean all MongoDB specific formats ($oid, $date)
to ensure correct Firestore columns/fields types for reports and history to work.
"""
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, ObjectId

def clean_doc(val):
    """
    Recursively clean MongoDB JSON exports:
    - Convert {'$oid': '...'} to string.
    - Convert {'$date': '...'} to datetime object.
    - Convert {'$binary': {'base64': '...'}} to decoded string.
    """
    if isinstance(val, dict):
        if '$oid' in val:
            return str(val['$oid'])
        if '$date' in val:
            date_str = val['$date']
            if isinstance(date_str, str):
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                try:
                    # Strip fractional seconds to fit standard isoformat if necessary
                    if '.' in date_str:
                        base, tz = date_str.split('+')
                        base = base.split('.')[0]
                        date_str = base + '+' + tz
                    return datetime.fromisoformat(date_str)
                except ValueError:
                    # Fallback to standard parsing
                    try:
                        return datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        return date_str
            return date_str
        if '$binary' in val:
            import base64
            return base64.b64decode(val['$binary']['base64']).decode('utf-8', errors='replace')
        return {k: clean_doc(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [clean_doc(item) for item in val]
    else:
        return val

def seed_firebase():
    print("Starting Firebase Firestore Seeding with Clean Columns...")
    
    collections = ['users', 'customers', 'items', 'invoices', 'settings']
    
    for col_name in collections:
        export_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'export_{col_name}.json')
        if os.path.exists(export_file):
            col = db[col_name]
            
            # Read existing documents to delete them first (to ensure fresh clean schema)
            try:
                existing_docs = col._read()
            except Exception:
                existing_docs = []
                
            if len(existing_docs) > 0:
                print(f"Clearing {len(existing_docs)} existing documents from '{col_name}' collection...")
                for doc in existing_docs:
                    try:
                        col.delete_one({"_id": doc["_id"]})
                    except Exception as e:
                        print(f"Error deleting doc {doc.get('_id')}: {e}")
            
            with open(export_file, 'r', encoding='utf-8') as f:
                try:
                    docs = json.load(f)
                except json.JSONDecodeError:
                    print(f"[ERROR] Could not parse {export_file}")
                    continue
            
            imported = 0
            for doc in docs:
                # Clean document recursively
                cleaned = clean_doc(doc)
                
                # Double-check invoice fields
                if col_name == 'invoices':
                    # Parse dates
                    for date_field in ['invoice_date', 'due_date', 'created_at']:
                        if date_field in cleaned and isinstance(cleaned[date_field], str):
                            try:
                                cleaned[date_field] = datetime.fromisoformat(cleaned[date_field].replace('Z', '+00:00'))
                            except Exception:
                                pass
                
                # Make sure _id is string at the top level
                if '_id' in cleaned:
                    cleaned['_id'] = str(cleaned['_id'])
                
                col.insert_one(cleaned)
                imported += 1
            
            print(f"[OK] Imported {imported} clean documents into Firebase collection '{col_name}'")
        else:
            print(f"[INFO] No export file found for '{col_name}' (expected: export_{col_name}.json)")
            
    print("\n[DONE] Firebase database seeding completed successfully!")

if __name__ == "__main__":
    seed_firebase()
