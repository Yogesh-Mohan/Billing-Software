"""
Script to export local MongoDB data to JSON files for migration to Atlas.
"""
import json
from pymongo import MongoClient
from bson import json_util

client = MongoClient('mongodb://localhost:27017/')
db = client['red_studio_billing']

collections = ['customers', 'items', 'invoices', 'users', 'settings']

for col_name in collections:
    col = db[col_name]
    docs = list(col.find())
    count = len(docs)
    
    with open(f'export_{col_name}.json', 'w', encoding='utf-8') as f:
        f.write(json_util.dumps(docs, indent=2, ensure_ascii=False))
    
    print(f"[OK] Exported {count} documents from '{col_name}'")

print("\nAll collections exported! Files saved in project folder.")
client.close()
