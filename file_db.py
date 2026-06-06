"""
File-based database adapter that mimics pymongo's interface.
Stores data in JSON files — no MongoDB required!
Works with PythonAnywhere (persistent files) and any hosting platform.
"""
import os
import json
import uuid
import re
import time
from datetime import datetime
from copy import deepcopy

class ProcessFileLock:
    """A simple cross-platform, cross-process lock using atomic directory creation."""
    def __init__(self, lock_path):
        self.lock_path = lock_path

    def acquire(self, timeout=10):
        start = time.time()
        while True:
            try:
                os.mkdir(self.lock_path)
                return True
            except FileExistsError:
                if time.time() - start > timeout:
                    try:
                        os.rmdir(self.lock_path)
                    except OSError:
                        pass
                else:
                    time.sleep(0.05)

    def release(self):
        try:
            os.rmdir(self.lock_path)
        except OSError:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class FileObjectId:
    """Mimics bson.ObjectId for file-based storage."""
    def __init__(self, oid=None):
        if oid is None:
            self._id = uuid.uuid4().hex[:24]
        elif isinstance(oid, FileObjectId):
            self._id = oid._id
        else:
            self._id = str(oid)

    def __str__(self):
        return self._id

    def __repr__(self):
        return f"FileObjectId('{self._id}')"

    def __eq__(self, other):
        if isinstance(other, FileObjectId):
            return self._id == other._id
        return self._id == str(other)

    def __hash__(self):
        return hash(self._id)


class FileCollection:
    """Mimics pymongo.Collection using a JSON file."""

    def __init__(self, db_path, name):
        self.name = name
        self.file_path = os.path.join(db_path, f"{name}.json")
        self._lock = ProcessFileLock(self.file_path + ".lock")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _read(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        # Convert date strings back to datetime objects
        for doc in data:
            for key, val in doc.items():
                if isinstance(val, str):
                    if val.startswith("__datetime__:"):
                        doc[key] = datetime.fromisoformat(val.replace("__datetime__:", ""))
                    elif key.endswith("_date") or key.endswith("_at"):
                        try:
                            doc[key] = datetime.fromisoformat(val.replace("Z", "+00:00")[:19])
                        except ValueError:
                            pass
                elif isinstance(val, dict):
                    for k2, v2 in val.items():
                        if isinstance(v2, str):
                            if v2.startswith("__datetime__:"):
                                val[k2] = datetime.fromisoformat(v2.replace("__datetime__:", ""))
                            elif k2.endswith("_date") or k2.endswith("_at"):
                                try:
                                    val[k2] = datetime.fromisoformat(v2.replace("Z", "+00:00")[:19])
                                except ValueError:
                                    pass
        return data

    def _write(self, data):
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return f"__datetime__:{obj.isoformat()}"
            if isinstance(obj, FileObjectId):
                return str(obj)
            if isinstance(obj, bytes):
                return obj.decode('utf-8', errors='replace')
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=default_serializer, ensure_ascii=False, indent=2)

    def _match(self, doc, query):
        """Check if a document matches a query filter."""
        if not query:
            return True

        for key, condition in query.items():
            if key == "$or":
                if not any(self._match(doc, sub_q) for sub_q in condition):
                    return False
                continue
            if key == "$and":
                if not all(self._match(doc, sub_q) for sub_q in condition):
                    return False
                continue

            # Handle nested dot notation (e.g., "customer.name")
            value = doc
            for part in key.split('.'):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break

            if isinstance(condition, dict):
                for op, op_val in condition.items():
                    # Helper for safe comparison
                    def safe_cmp(v1, v2, cmp_op):
                        if v1 is None:
                            return False
                        if type(v1) != type(v2):
                            if isinstance(v1, str) and isinstance(v2, datetime):
                                try:
                                    v1 = datetime.fromisoformat(v1.replace('Z', '+00:00')[:19])
                                except ValueError:
                                    pass
                        try:
                            if cmp_op == ">=": return v1 >= v2
                            if cmp_op == "<=": return v1 <= v2
                            if cmp_op == "<": return v1 < v2
                            if cmp_op == ">": return v1 > v2
                        except TypeError:
                            return False
                        return False

                    if op == "$regex":
                        flags = 0
                        if isinstance(condition.get("$options", ""), str) and "i" in condition.get("$options", ""):
                            flags = re.IGNORECASE
                        if value is None or not re.search(op_val, str(value), flags):
                            return False
                    elif op == "$gte":
                        if not safe_cmp(value, op_val, ">="):
                            return False
                    elif op == "$lte":
                        if not safe_cmp(value, op_val, "<="):
                            return False
                    elif op == "$lt":
                        if not safe_cmp(value, op_val, "<"):
                            return False
                    elif op == "$gt":
                        if not safe_cmp(value, op_val, ">"):
                            return False
                    elif op == "$ne":
                        if isinstance(op_val, FileObjectId):
                            if str(value) == str(op_val):
                                return False
                        elif value == op_val:
                            return False
                    elif op == "$sum":
                        pass  # Handled in aggregate
                    elif op == "$in":
                        if value not in op_val:
                            return False
            elif hasattr(condition, 'match'):
                # It's a compiled regex
                if value is None or not condition.search(str(value)):
                    return False
            elif isinstance(condition, FileObjectId):
                if str(value) != str(condition):
                    return False
            else:
                if str(value) != str(condition):
                    return False

        return True

    def find(self, query=None, projection=None):
        """Returns a FileCursor (chainable .sort(), .limit())."""
        with self._lock:
            data = self._read()
        results = [deepcopy(doc) for doc in data if self._match(doc, query or {})]
        return FileCursor(results)

    def find_one(self, query=None):
        with self._lock:
            data = self._read()
        for doc in data:
            if self._match(doc, query or {}):
                return deepcopy(doc)
        return None

    def insert_one(self, doc):
        doc = deepcopy(doc)
        if '_id' not in doc:
            doc['_id'] = str(FileObjectId())
        else:
            doc['_id'] = str(doc['_id'])
        with self._lock:
            data = self._read()
            data.append(doc)
            self._write(data)
        return InsertOneResult(doc['_id'])

    def update_one(self, query, update):
        with self._lock:
            data = self._read()
            for i, doc in enumerate(data):
                if self._match(doc, query):
                    if "$set" in update:
                        for k, v in update["$set"].items():
                            doc[k] = v
                    if "$inc" in update:
                        for k, v in update["$inc"].items():
                            doc[k] = doc.get(k, 0) + v
                    data[i] = doc
                    self._write(data)
                    return UpdateResult(1, 1)
            self._write(data)
        return UpdateResult(0, 0)

    def delete_one(self, query):
        with self._lock:
            data = self._read()
            for i, doc in enumerate(data):
                if self._match(doc, query):
                    data.pop(i)
                    self._write(data)
                    return DeleteResult(1)
        return DeleteResult(0)

    def count_documents(self, query=None):
        with self._lock:
            data = self._read()
        return sum(1 for doc in data if self._match(doc, query or {}))

    def aggregate(self, pipeline):
        """Simple aggregate support for $match, $group, $sort, $limit, $addFields."""
        with self._lock:
            data = self._read()
        docs = [deepcopy(d) for d in data]

        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if self._match(d, stage["$match"])]
            elif "$group" in stage:
                group = stage["$group"]
                group_id = group.get("_id")
                result = {}

                for doc in docs:
                    # For _id: None, group everything together
                    if group_id is None:
                        key = None
                    elif isinstance(group_id, dict) and "$dateToString" in group_id:
                        date_field = group_id["$dateToString"]["date"].replace("$", "")
                        dt_val = doc.get(date_field)
                        if isinstance(dt_val, datetime):
                            fmt = group_id["$dateToString"].get("format", "%Y-%m-%d")
                            key = dt_val.strftime(fmt)
                        else:
                            key = str(dt_val)
                    else:
                        key = str(doc.get(str(group_id).replace("$", ""), ""))
                    if key not in result:
                        result[key] = {"_id": key}
                    for field, expr in group.items():
                        if field == "_id":
                            continue
                        if isinstance(expr, dict) and "$sum" in expr:
                            sum_field = expr["$sum"]
                            if isinstance(sum_field, str) and sum_field.startswith("$"):
                                val = doc.get(sum_field[1:], 0)
                            else:
                                val = sum_field
                            result[key][field] = result[key].get(field, 0) + (val if isinstance(val, (int, float)) else 0)

                docs = list(result.values())
            elif "$sort" in stage:
                sort_field = list(stage["$sort"].keys())[0]
                reverse = list(stage["$sort"].values())[0] == -1
                docs.sort(key=lambda x: (x.get(sort_field) is None, x.get(sort_field, "")), reverse=reverse)
            elif "$limit" in stage:
                docs = docs[:stage["$limit"]]
            elif "$addFields" in stage:
                for doc in docs:
                    for field, expr in stage["$addFields"].items():
                        if isinstance(expr, dict) and "$toInt" in expr:
                            src = expr["$toInt"]
                            if isinstance(src, str) and src.startswith("$"):
                                try:
                                    doc[field] = int(doc.get(src[1:], 0))
                                except (ValueError, TypeError):
                                    doc[field] = 0

        return docs


class FileCursor:
    """Mimics pymongo.Cursor with sort/limit chaining."""

    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=1):
        reverse = direction == -1
        self._docs.sort(
            key=lambda x: (x.get(field) is None, x.get(field, "")),
            reverse=reverse
        )
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self):
        return len(self._docs)

    def __list__(self):
        return self._docs


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class DeleteResult:
    def __init__(self, deleted):
        self.deleted_count = deleted


class FileDatabase:
    """Mimics pymongo database — access collections as attributes."""

    def __init__(self, db_path):
        self._db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        if name not in self._collections:
            self._collections[name] = FileCollection(self._db_path, name)
        return self._collections[name]

    def __getitem__(self, name):
        return self.__getattr__(name)


class FileClient:
    """Mimics pymongo.MongoClient for file-based storage."""

    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def __getitem__(self, db_name):
        db_path = os.path.join(self._data_dir, db_name)
        return FileDatabase(db_path)

    def server_info(self):
        return {"version": "file-db-1.0", "ok": 1.0}

    def close(self):
        pass
