"""
Seed the Firebase Firestore database with exported data from JSON files.
This will create all collections (tables) and import the rows and columns of data.
"""
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, ObjectId

def seed_firebase():
    print("Starting Firebase Firestore Seeding...")
    
    collections = ['users', 'customers', 'items', 'invoices', 'settings']
    
    for col_name in collections:
        export_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'export_{col_name}.json')
        if os.path.exists(export_file):
            # Get the firestore collection
            col = db[col_name]
            
            # Check if there are already documents
            try:
                existing_docs = col._read()
            except Exception as e:
                existing_docs = []
            
            if len(existing_docs) > 0:
                print(f"[SKIP] '{col_name}' already has {len(existing_docs)} documents in Firebase.")
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
                        # Convert ISO format string to Python datetime
                        date_str = val['$date']
                        if date_str.endswith('Z'):
                            date_str = date_str[:-1] + '+00:00'
                        try:
                            doc[key] = datetime.fromisoformat(date_str)
                        except ValueError:
                            doc[key] = date_str
                    elif isinstance(val, dict) and '$binary' in val:
                        # Handle binary fields
                        import base64
                        doc[key] = base64.b64decode(val['$binary']['base64']).decode('utf-8', errors='replace')
                
                # If it's the invoices collection, parse nested dates and item ObjectIds if needed
                if col_name == 'invoices':
                    if 'invoice_date' in doc and isinstance(doc['invoice_date'], str):
                        try:
                            doc['invoice_date'] = datetime.fromisoformat(doc['invoice_date'].replace('Z', '+00:00'))
                        except Exception:
                            pass
                    if 'due_date' in doc and isinstance(doc['due_date'], str):
                        try:
                            doc['due_date'] = datetime.fromisoformat(doc['due_date'].replace('Z', '+00:00'))
                        except Exception:
                            pass
                
                col.insert_one(doc)
                imported += 1
            
            print(f"[OK] Imported {imported} documents into Firebase collection '{col_name}'")
        else:
            print(f"[INFO] No export file found for '{col_name}' (expected: export_{col_name}.json)")
            
    print("\n[DONE] Firebase database seeding completed!")

if __name__ == "__main__":
    seed_firebase()
