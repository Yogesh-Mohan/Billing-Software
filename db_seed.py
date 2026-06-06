import bcrypt
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
from config import Config

def seed_database():
    print("Connecting to MongoDB...")
    client = MongoClient(Config.MONGO_URI)
    db = client[Config.DB_NAME]
    
    # 1. Create Indexes
    print("Creating collections and indexes...")
    db.users.create_index("username", unique=True)
    db.customers.create_index("name")
    db.products.create_index("product_code", unique=True)
    db.products.create_index("product_name")
    db.items.create_index("item_code", unique=True)
    db.invoices.create_index("invoice_number", unique=True)
    db.invoices.create_index("invoice_date")
    
    # 2. Seed Admin User
    print("Checking admin user...")
    admin_user = db.users.find_one({"username": "admin"})
    if not admin_user:
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(b"admin123", salt).decode('utf-8')
        db.users.insert_one({
            "username": "admin",
            "password": hashed_password,
            "created_at": datetime.utcnow()
        })
        print("Admin user ('admin' / 'admin123') created successfully!")
    else:
        print("Admin user already exists.")
        
    # 3. Seed Default Business Settings
    print("Checking business settings...")
    settings_count = db.settings.count_documents({})
    if settings_count == 0:
        db.settings.insert_one({
            "business_name": "RED STUDIO",
            "logo_path": "",
            "address": "123 Creative Street, Tech Hub, Chennai, Tamil Nadu",
            "phone": "+91 98765 43210",
            "email": "contact@redstudio.com",
            "gst_number": "33AAAAA1111A1Z1"
        })
        print("Default business settings created successfully!")
    else:
        print("Business settings already exist.")

    # 4. Seed Sample Customers (optional if clean, but requested in deliverables)
    if db.customers.count_documents({}) == 0:
        print("Seeding sample customers...")
        db.customers.insert_many([
            {
                "name": "Aravind Kumar",
                "phone": "9876543211",
                "email": "aravind@gmail.com",
                "address": "45, Gandhi Nagar, Chennai",
                "created_at": datetime.utcnow()
            },
            {
                "name": "Priya Sharma",
                "phone": "9812345678",
                "email": "priya.sharma@yahoo.com",
                "address": "12, Outer Ring Road, Bangalore",
                "created_at": datetime.utcnow()
            }
        ])
        print("Sample customers seeded!")

    # 5. Seed Sample Products
    if db.products.count_documents({}) == 0:
        print("Seeding sample products...")
        db.products.insert_many([
            {
                "product_name": "Professional Video Camera",
                "product_code": "PRO-CAM-01",
                "category": "Equipment",
                "price": 85000.0,
                "stock_quantity": 4,
                "created_at": datetime.utcnow()
            },
            {
                "product_name": "LED Studio Lighting Kit",
                "product_code": "STUDIO-LED-05",
                "category": "Lighting",
                "price": 15000.0,
                "stock_quantity": 12,
                "created_at": datetime.utcnow()
            },
            {
                "product_name": "Condenser Microphone set",
                "product_code": "MIC-COND-03",
                "category": "Audio",
                "price": 8500.0,
                "stock_quantity": 8,
                "created_at": datetime.utcnow()
            },
            {
                "product_name": "SD Card 128GB High Speed",
                "product_code": "SD-128GB",
                "category": "Accessories",
                "price": 2200.0,
                "stock_quantity": 40,
                "created_at": datetime.utcnow()
            }
        ])
        print("Sample products seeded!")

    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
