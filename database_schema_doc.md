# RED STUDIO - Database Schema Documentation

Since RED STUDIO uses **Firebase Firestore**, a flexible NoSQL cloud database, data is stored in Firestore collections instead of SQL tables. Below is the schema documentation representing the collections, field types, and relations.

---

## 1. `users` Collection
Stores information for authentication.
```json
{
  "_id": "ObjectId",
  "username": "string (unique)",
  "password": "string (bcrypt hashed)",
  "created_at": "datetime"
}
```

## 2. `customers` Collection
Stores customer profiles.
```json
{
  "_id": "ObjectId",
  "name": "string",
  "phone": "string",
  "email": "string",
  "address": "string",
  "created_at": "datetime"
}
```

## 3. `products` Collection
Stores product inventory and catalog items.
```json
{
  "_id": "ObjectId",
  "product_name": "string",
  "product_code": "string (unique)",
  "category": "string",
  "price": "double",
  "stock_quantity": "int",
  "created_at": "datetime"
}
```

## 4. `invoices` Collection
Stores generated invoices. Invoice items are embedded directly inside the document for high-performance retrieval and historical price consistency.
```json
{
  "_id": "ObjectId",
  "invoice_number": "string (unique, generated e.g., INV-YYYYMMDD-XXXX)",
  "invoice_date": "datetime",
  "customer": {
    "customer_id": "ObjectId",
    "name": "string",
    "phone": "string",
    "email": "string",
    "address": "string"
  },
  "items": [
    {
      "product_id": "ObjectId",
      "product_name": "string",
      "product_code": "string",
      "quantity": "int",
      "price": "double",
      "subtotal": "double"
    }
  ],
  "subtotal": "double",
  "tax_rate": "double (e.g. 18.0)",
  "tax_amount": "double",
  "grand_total": "double",
  "created_at": "datetime"
}
```

## 5. `settings` Collection
Stores global business details shown on invoices and reports.
```json
{
  "_id": "ObjectId",
  "business_name": "string",
  "logo_path": "string",
  "address": "string",
  "phone": "string",
  "email": "string",
  "gst_number": "string"
}
```
