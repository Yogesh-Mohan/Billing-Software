# Firebase database adapter using Firebase Admin SDK
import os
import json
from datetime import datetime
from copy import deepcopy
import firebase_admin
from firebase_admin import credentials, firestore
from file_db import FileCollection, FileCursor, FileObjectId, InsertOneResult, UpdateResult, DeleteResult

class DummyLock:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class FirestoreCollection(FileCollection):
    def __init__(self, db, name):
        self.name = name
        self.collection_ref = db.collection(name)
        self._lock = DummyLock()

    def _read(self):
        docs = []
        for doc in self.collection_ref.stream():
            data = doc.to_dict()
            data['_id'] = doc.id
            
            # Convert Firestore timestamps to python datetime objects
            for key, val in data.items():
                if hasattr(val, 'timestamp'):  # Timestamp objects from Firestore SDK
                    data[key] = val.replace(tzinfo=None)
                elif isinstance(val, dict):
                    for k2, v2 in val.items():
                        if hasattr(v2, 'timestamp'):
                            val[k2] = v2.replace(tzinfo=None)
            docs.append(data)
        return docs

    def _serialize_doc(self, doc):
        serialized = {}
        for k, v in doc.items():
            if isinstance(v, dict):
                serialized[k] = self._serialize_doc(v)
            elif isinstance(v, list):
                serialized[k] = [
                    self._serialize_doc(item) if isinstance(item, dict)
                    else (str(item) if isinstance(item, FileObjectId) else item)
                    for item in v
                ]
            elif isinstance(v, FileObjectId):
                serialized[k] = str(v)
            else:
                serialized[k] = v
        return serialized

    def insert_one(self, doc):
        doc = deepcopy(doc)
        if '_id' not in doc:
            doc['_id'] = str(FileObjectId())
        else:
            doc['_id'] = str(doc['_id'])
        
        doc_id = doc['_id']
        self.collection_ref.document(doc_id).set(self._serialize_doc(doc))
        return InsertOneResult(doc_id)

    def update_one(self, query, update):
        matched_doc = self.find_one(query)
        if not matched_doc:
            return UpdateResult(0, 0)
        
        doc_id = matched_doc['_id']
        
        # Apply $set and $inc operations locally
        if "$set" in update:
            for k, v in update["$set"].items():
                matched_doc[k] = v
        if "$inc" in update:
            for k, v in update["$inc"].items():
                matched_doc[k] = matched_doc.get(k, 0) + v
                
        self.collection_ref.document(doc_id).set(self._serialize_doc(matched_doc))
        return UpdateResult(1, 1)

    def delete_one(self, query):
        matched_doc = self.find_one(query)
        if not matched_doc:
            return DeleteResult(0)
        
        doc_id = matched_doc['_id']
        self.collection_ref.document(doc_id).delete()
        return DeleteResult(1)


class FirestoreDatabase:
    def __init__(self, db):
        self._db = db
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        if name not in self._collections:
            self._collections[name] = FirestoreCollection(self._db, name)
        return self._collections[name]

    def __getitem__(self, name):
        return self.__getattr__(name)


class FirestoreClient:
    def __init__(self, credentials_json=None):
        if not firebase_admin._apps:
            if credentials_json:
                try:
                    creds_dict = json.loads(credentials_json)
                    cred = credentials.Certificate(creds_dict)
                    firebase_admin.initialize_app(cred)
                except Exception as e:
                    print(f"[ERROR] Failed to initialize Firebase with Service Account: {e}")
                    firebase_admin.initialize_app()
            else:
                firebase_admin.initialize_app()
        self._db = firestore.client()

    def __getitem__(self, db_name):
        return FirestoreDatabase(self._db)

    def server_info(self):
        return {"version": "firestore-1.0", "ok": 1.0}

    def close(self):
        pass
