import os
import re
import csv
import json
from io import StringIO
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response, send_from_directory, send_file
from werkzeug.utils import secure_filename
from file_db import FileClient, FileObjectId
ObjectId = FileObjectId
import bcrypt
from config import Config
from ledger_utils import read_ledger, add_ledger_entry, update_ledger_entry, delete_ledger_entry, MONTH_NAMES

# Install reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
except ImportError:
    pass

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database Setup — Try Firebase first, fall back to file-based DB
USE_FILE_DB = False
USE_FIREBASE = False
firebase_creds = os.environ.get('FIREBASE_SERVICE_ACCOUNT')

if not firebase_creds:
    # Fallback to local service account file if it exists
    local_key_path = os.path.join(app.root_path, 'billingsystem-e4961-firebase-adminsdk-fbsvc-c057a349ef.json')
    if os.path.exists(local_key_path):
        try:
            with open(local_key_path, 'r', encoding='utf-8') as f:
                firebase_creds = f.read()
        except Exception as e:
            print(f"[WARN] Failed to read local Firebase key file: {e}")

if firebase_creds:
    try:
        from firebase_db import FirestoreClient
        client = FirestoreClient(firebase_creds)
        db = client[app.config.get('DB_NAME', 'red_studio_billing')]
        USE_FIREBASE = True
        print("[OK] Connected to Firebase Firestore successfully!")
    except Exception as e:
        print(f"[WARN] Cannot connect to Firebase: {e}")

if not USE_FIREBASE:
    USE_FILE_DB = True
    data_dir = os.path.join(app.root_path, 'data')
    client = FileClient(data_dir)
    db = client[app.config.get('DB_NAME', 'red_studio_billing')]
    print(f"[OK] File-based database ready at: {data_dir}")

# Helper to check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper: Load business settings globally for templates
@app.context_processor
def inject_settings():
    settings = db.settings.find_one({})
    if not settings:
        settings = {
            "business_name": "RED STUDIO",
            "logo_path": "",
            "address": "123 Creative Street, Tech Hub",
            "phone": "+91 98765 43210",
            "email": "contact@redstudio.com",
            "gst_number": ""
        }
    return dict(business_settings=settings)

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('hub'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('All fields are required.', 'danger')
            return render_template('login.html')
            
        user = db.users.find_one({"username": username})
        
        if user:
            # Fix #1: user['password'] from MongoDB is already bytes, don't call .encode()
            stored_pw = user['password'] if isinstance(user['password'], bytes) else user['password'].encode('utf-8')
            if bcrypt.checkpw(password.encode('utf-8'), stored_pw):
                session['logged_in'] = True
                session['username'] = username
                flash('Welcome back to RED STUDIO!', 'success')
                return redirect(url_for('hub'))
            else:
                flash('Invalid username or password.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ==========================================
# HUB & APPS
# ==========================================
@app.route('/')
@login_required
def hub():
    return render_template('hub.html')

@app.route('/ledger')
@login_required
def ledger():
    entries, monthly_summary = read_ledger('2026')
    filter_month = request.args.get('month', 'all')
    
    if filter_month != 'all':
        entries = [e for e in entries if e['month'].lower() == filter_month.lower()]
    
    # Calculate totals
    totals = {
        'revenue': sum(e['revenue'] for e in entries),
        'expenditures': sum(e['expenditures'] for e in entries),
        'investment': sum(e['investment'] for e in entries),
        'salary': sum(e['salary'] for e in entries),
    }
    totals['balance'] = totals['revenue'] - totals['expenditures'] - totals['investment'] - totals['salary']
    
    return render_template('ledger.html', 
        entries=entries, 
        monthly_summary=monthly_summary,
        totals=totals, 
        filter_month=filter_month,
        months=MONTH_NAMES
    )

@app.route('/ledger/add', methods=['POST'])
@login_required
def ledger_add():
    month_num = int(request.form.get('month', 1))
    date_str = request.form.get('date', '')
    name = request.form.get('name', '').strip()
    entry_type = request.form.get('type', '').strip()
    revenue = request.form.get('revenue', '')
    expenditures = request.form.get('expenditures', '')
    investment = request.form.get('investment', '')
    salary = request.form.get('salary', '')
    payment_method = request.form.get('payment_method', '').strip()
    
    if not name:
        flash('Name is required.', 'danger')
        return redirect(url_for('ledger'))
    
    success, msg = add_ledger_entry(
        month_num, date_str, name, entry_type,
        revenue, expenditures, investment, salary, payment_method
    )
    
    if success:
        flash('Entry added to ledger successfully!', 'success')
    else:
        flash(f'Error: {msg}', 'danger')
    
    return redirect(url_for('ledger'))

@app.route('/ledger/edit', methods=['POST'])
@login_required
def ledger_edit():
    row_num = int(request.form.get('row', 0))
    date_str = request.form.get('date', '')
    name = request.form.get('name', '').strip()
    entry_type = request.form.get('type', '').strip()
    revenue = request.form.get('revenue', '')
    expenditures = request.form.get('expenditures', '')
    investment = request.form.get('investment', '')
    salary = request.form.get('salary', '')
    payment_method = request.form.get('payment_method', '').strip()
    
    if row_num <= 0:
        flash('Invalid entry.', 'danger')
        return redirect(url_for('ledger'))
    
    success, msg = update_ledger_entry(
        row_num, date_str, name, entry_type,
        revenue, expenditures, investment, salary, payment_method
    )
    
    if success:
        flash('Entry updated successfully!', 'success')
    else:
        flash(f'Error: {msg}', 'danger')
    
    return redirect(url_for('ledger'))

@app.route('/ledger/delete/<int:row_num>', methods=['POST'])
@login_required
def ledger_delete(row_num):
    success, msg = delete_ledger_entry(row_num)
    if success:
        flash('Entry deleted successfully!', 'success')
    else:
        flash(f'Error: {msg}', 'danger')
    return redirect(url_for('ledger'))

@app.route('/ledger/export')
@login_required
def ledger_export():
    from ledger_utils import EXCEL_PATH
    return send_file(
        EXCEL_PATH, 
        as_attachment=True, 
        download_name=f"Redwed_Ledger_{datetime.now().strftime('%Y_%m_%d')}.xlsx"
    )

@app.route('/api/ledger/summary')
@login_required
def ledger_summary_api():
    """API endpoint for ledger monthly summary (used by dashboard)."""
    _, monthly_summary = read_ledger('2026')
    return jsonify(monthly_summary)

@app.route('/events')
@login_required
def events():
    return render_template('events.html')

# ==========================================
# DASHBOARD ROUTE
# ==========================================
@app.route('/dashboard')
@login_required
def dashboard():
    # Fetch Counts
    total_customers = db.customers.count_documents({})
    total_products = db.products.count_documents({})
    total_invoices = db.invoices.count_documents({})
    
    # Calculate Total Sales (Sum of grand_total of all invoices)
    sales_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}]
    sales_result = list(db.invoices.aggregate(sales_pipeline))
    total_sales = sales_result[0]['total'] if sales_result else 0.0
    
    # Recent Invoices (limit 5)
    recent_invoices = list(db.invoices.find().sort("invoice_date", -1).limit(5))
    
    # Low stock warnings
    low_stock_products = list(db.products.find({"stock_quantity": {"$lte": app.config['LOW_STOCK_THRESHOLD']}}))
    
    # Monthly sales data for graph (last 6 months)
    # Fix #9: Use proper modular arithmetic to avoid wrong month/year calculation
    graph_data = []
    today = datetime.utcnow()
    for i in range(5, -1, -1):
        # Compute correct year and month using total months offset
        total_months = today.year * 12 + today.month - i - 1
        year = total_months // 12
        month = total_months % 12 + 1
        
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
            
        month_sales = list(db.invoices.aggregate([
            {"$match": {"invoice_date": {"$gte": start_date, "$lt": end_date}}},
            {"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}
        ]))
        
        month_total = month_sales[0]['total'] if month_sales else 0.0
        month_name = start_date.strftime("%b %Y")
        graph_data.append({"month": month_name, "total": month_total})
        
    return render_template('dashboard.html', 
                           total_customers=total_customers, 
                           total_products=total_products, 
                           total_invoices=total_invoices, 
                           total_sales=total_sales,
                           recent_invoices=recent_invoices,
                           low_stock_products=low_stock_products,
                           graph_data=graph_data)

# ==========================================
# CUSTOMER MANAGEMENT ROUTES
# ==========================================
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        if not name or not phone:
            flash('Customer Name and Phone Number are required.', 'danger')
            return redirect(url_for('customers'))
            
        if action == 'add':
            db.customers.insert_one({
                "name": name,
                "phone": phone,
                "email": email,
                "address": address,
                "created_at": datetime.utcnow()
            })
            flash('Customer added successfully!', 'success')
        elif action == 'edit':
            customer_id = request.form.get('customer_id')
            if customer_id:
                try:
                    db.customers.update_one(
                        {"_id": ObjectId(customer_id)},
                        {"$set": {"name": name, "phone": phone, "email": email, "address": address}}
                    )
                    flash('Customer updated successfully!', 'success')
                except Exception as e:
                    flash('Error updating customer.', 'danger')
                
        return redirect(url_for('customers'))
        
    # GET: fetch and search
    search_query = request.args.get('search', '').strip()
    if search_query:
        # Fix #12: Escape user input to prevent ReDoS vulnerability
        rgx = re.compile(re.escape(search_query), re.IGNORECASE)
        base_customer_list = list(db.customers.find({
            "$or": [{"name": rgx}, {"phone": rgx}, {"email": rgx}]
        }).sort("name", 1))
    else:
        base_customer_list = list(db.customers.find().sort("name", 1))
        
    # Enhance customer list with invoice data
    customer_list = []
    for cust in base_customer_list:
        # Find all invoices for this customer
        invoices = list(db.invoices.find({"customer.name": cust["name"]}).sort("invoice_date", -1))
        
        balance = sum(inv.get("grand_total", 0) for inv in invoices)
        
        last_invoice = ""
        due_date = ""
        salesperson = ""
        payment_method = ""
        
        if invoices:
            last_invoice = invoices[0].get("invoice_number", "")
            salesperson = invoices[0].get("salesperson", "")
            payment_method = invoices[0].get("payment_terms", "")
            
            # Find earliest due date among invoices
            # For simplicity, just use the due date of the most recent invoice, or None
            # If we had unpaid status, we'd find the earliest unpaid invoice.
            due_date_obj = invoices[0].get("due_date")
            if due_date_obj:
                due_date = due_date_obj.strftime("%d-%m-%Y")
                
        cust_enriched = {
            "_id": cust["_id"],
            "name": cust["name"],
            "email": cust.get("email", ""),
            # Fix #6: Include phone and address so edit modal can populate them
            "phone": cust.get("phone", ""),
            "address": cust.get("address", ""),
            "balance": balance,
            "due_date": due_date,
            "last_invoice": last_invoice,
            "salesperson": salesperson,
            "payment_method": payment_method,
            "group": "Default"
        }
        customer_list.append(cust_enriched)
        
    return render_template('customers.html', customers=customer_list, search_query=search_query)

@app.route('/customers/delete/<customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    try:
        db.customers.delete_one({"_id": ObjectId(customer_id)})
        flash('Customer deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting customer.', 'danger')
    return redirect(url_for('customers'))

# ==========================================
# PRODUCT MANAGEMENT ROUTES
# ==========================================
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    if request.method == 'POST':
        action = request.form.get('action')
        product_name = request.form.get('product_name', '').strip()
        product_code = request.form.get('product_code', '').strip().upper()
        category = request.form.get('category', '').strip()
        
        try:
            price = float(request.form.get('price', 0))
            stock_quantity = int(request.form.get('stock_quantity', 0))
        except ValueError:
            flash('Invalid price or stock level.', 'danger')
            return redirect(url_for('products'))
            
        if not product_name or not product_code or price <= 0:
            flash('Product Name, Code and valid Price are required.', 'danger')
            return redirect(url_for('products'))
            
        if action == 'add':
            # Check for duplicate code
            if db.products.find_one({"product_code": product_code}):
                flash(f'Product Code "{product_code}" already exists.', 'danger')
                return redirect(url_for('products'))
                
            db.products.insert_one({
                "product_name": product_name,
                "product_code": product_code,
                "category": category,
                "price": price,
                "stock_quantity": stock_quantity,
                "created_at": datetime.utcnow()
            })
            flash('Product added successfully!', 'success')
        elif action == 'edit':
            product_id = request.form.get('product_id')
            if product_id:
                try:
                    # Check duplicate code excluding current
                    existing = db.products.find_one({"product_code": product_code, "_id": {"$ne": ObjectId(product_id)}})
                    if existing:
                        flash(f'Product Code "{product_code}" already exists.', 'danger')
                        return redirect(url_for('products'))
                        
                    db.products.update_one(
                        {"_id": ObjectId(product_id)},
                        {"$set": {
                            "product_name": product_name,
                            "product_code": product_code,
                            "category": category,
                            "price": price,
                            "stock_quantity": stock_quantity
                        }}
                    )
                    flash('Product updated successfully!', 'success')
                except Exception as e:
                    flash('Error updating product.', 'danger')
                
        return redirect(url_for('products'))
        
    search_query = request.args.get('search', '').strip()
    if search_query:
        # Fix #12: Escape user input to prevent ReDoS vulnerability
        rgx = re.compile(re.escape(search_query), re.IGNORECASE)
        product_list = list(db.products.find({
            "$or": [{"product_name": rgx}, {"product_code": rgx}, {"category": rgx}]
        }).sort("product_name", 1))
    else:
        product_list = list(db.products.find().sort("product_name", 1))
        
    return render_template('products.html', products=product_list, search_query=search_query)

@app.route('/products/delete/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    try:
        db.products.delete_one({"_id": ObjectId(product_id)})
        flash('Product deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting product.', 'danger')
    return redirect(url_for('products'))

# ==========================================
# INVOICE CREATION & LISTING ROUTES
# ==========================================
@app.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        billing_address = request.form.get('billing_address', '').strip()
        invoice_date_str = request.form.get('invoice_date')
        invoice_number = request.form.get('invoice_number', '').strip()
        tax_rate = float(request.form.get('tax_rate', 0))
        
        # New Metadata fields
        payment_terms = request.form.get('payment_terms', 'Pay in Days')
        payment_days = request.form.get('payment_days', '30')
        po_number = request.form.get('po_number', '').strip()
        salesperson = request.form.get('salesperson', '').strip()
        shipping_address = request.form.get('shipping_address', '').strip()
        public_note = request.form.get('public_note', '').strip()
        private_note = request.form.get('private_note', '').strip()
        foot_note = request.form.get('foot_note', '').strip()
        
        # Lists of item details
        product_ids = request.form.getlist('item_product_id[]')
        item_codes = request.form.getlist('item_code[]')
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        prices = request.form.getlist('item_price[]')
        discounts = request.form.getlist('item_discount[]')
        
        if not customer_name or not product_ids:
            flash('Customer Name and at least one Product are required.', 'danger')
            return redirect(url_for('create_invoice'))
            
        # Get or Create Customer Info
        customer = db.customers.find_one({"name": {"$regex": f"^{re.escape(customer_name)}$", "$options": "i"}})
        if not customer:
            customer_doc = {
                "name": customer_name,
                "address": billing_address,
                "phone": "",
                "email": "",
                "created_at": datetime.utcnow()
            }
            res = db.customers.insert_one(customer_doc)
            customer = db.customers.find_one({"_id": res.inserted_id})
        else:
            if billing_address:
                db.customers.update_one({"_id": customer["_id"]}, {"$set": {"address": billing_address}})
                customer["address"] = billing_address
            
        # Build Items list and deduct stock
        items = []
        subtotal = 0.0
        
        # Verify stock and prepare update operations
        stock_updates = []
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            try:
                qty = int(quantities[i])
                price = float(prices[i])
            except (ValueError, IndexError):
                flash('Invalid quantity or price provided.', 'danger')
                return redirect(url_for('create_invoice'))
            
            code = item_codes[i] if i < len(item_codes) else ''
            desc = descriptions[i] if i < len(descriptions) else ''
            
            try:
                db_item = db.items.find_one({"_id": ObjectId(pid)})
            except Exception:
                db_item = None
            
            if not db_item:
                flash('One or more selected items does not exist.', 'danger')
                return redirect(url_for('create_invoice'))
                
            if db_item.get('manage_stock') and db_item.get('current_qty', 0) < qty:
                flash(f"Insufficient stock for {db_item.get('item_name', 'Item')}. Only {db_item.get('current_qty', 0)} remaining.", 'danger')
                return redirect(url_for('create_invoice'))
                
            item_subtotal = qty * price
            discount_pct = float(discounts[i]) if i < len(discounts) else 0.0
            discount_amount = item_subtotal * (discount_pct / 100.0)
            item_after_discount = item_subtotal - discount_amount
            subtotal += item_after_discount
            
            items.append({
                "product_id": ObjectId(pid),
                "product_name": db_item.get('item_name', ''),
                "product_code": code,
                "description": desc,
                "quantity": qty,
                "price": price,
                "discount_pct": discount_pct,
                "discount_amount": discount_amount,
                "subtotal": item_after_discount
            })
            
            if db_item.get('manage_stock'):
                stock_updates.append((ObjectId(pid), qty))
            
        if not items:
            flash('Please add valid items to the invoice.', 'danger')
            return redirect(url_for('create_invoice'))
            
        # Calculate Tax & Total
        tax_amount = subtotal * (tax_rate / 100.0)
        grand_total = subtotal + tax_amount
        
        amount_paid_str = request.form.get('amount_paid', '0').strip()
        try:
            amount_paid = float(amount_paid_str) if amount_paid_str else 0.0
        except ValueError:
            amount_paid = 0.0
            
        balance_due = max(0.0, grand_total - amount_paid)
        
        # Generate Invoice Number automatically if not specified manually
        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d') if invoice_date_str else datetime.utcnow()
        if not invoice_number:
            # Fix #22: Sort numerically using $toInt aggregation to avoid string sort issues
            last_inv_agg = list(db.invoices.aggregate([
                {"$addFields": {"inv_num_int": {"$toInt": "$invoice_number"}}},
                {"$sort": {"inv_num_int": -1}},
                {"$limit": 1}
            ]))
            try:
                if last_inv_agg:
                    last_num = int(last_inv_agg[0]['invoice_number'])
                    invoice_number = str(last_num + 1)
                else:
                    invoice_number = "10000"
            except (ValueError, KeyError):
                invoice_number = "10000"
        else:
            # Check manual invoice number uniqueness
            if db.invoices.find_one({"invoice_number": invoice_number}):
                flash(f'Invoice Number "{invoice_number}" already exists.', 'danger')
                return redirect(url_for('create_invoice'))
        
        # Insert Invoice Document
        try:
            payment_days_int = int(payment_days) if payment_days else 30
        except ValueError:
            payment_days_int = 30
        due_date = invoice_date + timedelta(days=payment_days_int)
        
        invoice_doc = {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "payment_terms": payment_terms,
            "payment_days": payment_days,
            "po_number": po_number,
            "salesperson": salesperson,
            "shipping_address": shipping_address,
            "public_note": public_note,
            "private_note": private_note,
            "foot_note": foot_note,
            "customer": {
                "customer_id": customer['_id'],
                "name": customer['name'],
                # Fix #2: Use .get() to avoid KeyError if fields are missing
                "phone": customer.get('phone', ''),
                "email": customer.get('email', ''),
                "address": customer.get('address', '')
            },
            "items": items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "grand_total": grand_total,
            "amount_paid": amount_paid,
            "balance_due": balance_due,
            "created_at": datetime.utcnow()
        }
        
        res = db.invoices.insert_one(invoice_doc)
        
        # Deduct Product Stock levels
        for pid, qty in stock_updates:
            db.items.update_one(
                {"_id": pid},
                {"$inc": {"current_qty": -qty}}
            )
            
        flash(f'Invoice {invoice_number} generated successfully!', 'success')
        # After creating the invoice, redirect to the PDF download for immediate professional copy
        return redirect(url_for('download_invoice_pdf', invoice_id=str(res.inserted_id)))
        
    # GET Methods
    customers_list = list(db.customers.find().sort("name", 1))
    items_list = list(db.items.find().sort("item_code", 1))
    
    # Pre-serialize items and customers as JSON for the template script block
    items_json = json.dumps([
        {
            "id": str(item['_id']),
            "name": item.get('item_name', ''),
            "code": item.get('item_code', ''),
            "description": item.get('description', ''),
            "price": item.get('price', 0),
            "stock": item.get('current_qty', 0) if item.get('manage_stock') else -1
        }
        for item in items_list
    ])
    
    customers_json = json.dumps({
        cust['name']: {
            "address": cust.get('address', '').replace('\n', ' '),
            "phone": cust.get('phone', ''),
            "email": cust.get('email', '')
        }
        for cust in customers_list
    })
    
    # Pre-populate date and default next invoice number
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    # Fix #22: Use numeric sort via aggregation
    last_inv_agg = list(db.invoices.aggregate([
        {"$addFields": {"inv_num_int": {"$toInt": "$invoice_number"}}},
        {"$sort": {"inv_num_int": -1}},
        {"$limit": 1}
    ]))
    try:
        if last_inv_agg:
            last_num = int(last_inv_agg[0]['invoice_number'])
            suggested_invoice_num = str(last_num + 1)
        else:
            suggested_invoice_num = "10000"
    except (ValueError, KeyError):
        suggested_invoice_num = "10000"
    
    tmpl = render_template
    return tmpl('invoice_create.html', customers=customers_list, items=items_list, items_json=items_json, customers_json=customers_json, today=today_str, suggested_invoice_num=suggested_invoice_num)


@app.route('/invoices')
@login_required
def invoices():
    # Filtering / Searching
    search_query = request.args.get('search', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    
    query = {}
    
    if search_query:
        # Fix #12: Escape user input to prevent ReDoS vulnerability
        rgx = re.compile(re.escape(search_query), re.IGNORECASE)
        query["$or"] = [
            {"invoice_number": rgx},
            {"customer.name": rgx},
            {"customer.phone": rgx}
        ]
        
    if start_date_str or end_date_str:
        date_query = {}
        if start_date_str:
            date_query["$gte"] = datetime.strptime(start_date_str, '%Y-%m-%d')
        if end_date_str:
            # inclusive of the end date
            date_query["$lte"] = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        query["invoice_date"] = date_query
        
    invoices_list = list(db.invoices.find(query).sort("invoice_date", -1))
    return render_template('invoices.html', invoices=invoices_list, 
                           search_query=search_query, start_date=start_date_str, end_date=end_date_str)

@app.route('/invoices/<invoice_id>')
@login_required
def invoice_view(invoice_id):
    try:
        invoice = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except Exception:
        invoice = None
    
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices'))
    return render_template('invoice_view.html', invoice=invoice)

@app.route('/invoices/delete/<invoice_id>', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    try:
        invoice = db.invoices.find_one({"_id": ObjectId(invoice_id)})
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices'))
        
        # Restore stock quantities
        for item in invoice.get('items', []):
            if 'product_id' in item and item['product_id']:
                try:
                    db.items.update_one(
                        {"_id": item['product_id'], "manage_stock": True},
                        {"$inc": {"current_qty": item.get('quantity', 0)}}
                    )
                except Exception:
                    pass
        
        # Delete invoice
        db.invoices.delete_one({"_id": ObjectId(invoice_id)})
        flash('Invoice deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting invoice.', 'danger')
    return redirect(url_for('invoices'))

@app.route('/invoice/edit/<invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    try:
        invoice = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except Exception:
        invoice = None
        
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices'))
        
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        billing_address = request.form.get('billing_address', '').strip()
        invoice_date_str = request.form.get('invoice_date')
        tax_rate = float(request.form.get('tax_rate', 0))
        
        payment_terms = request.form.get('payment_terms', 'Pay in Days')
        payment_days = request.form.get('payment_days', '30')
        po_number = request.form.get('po_number', '').strip()
        salesperson = request.form.get('salesperson', '').strip()
        shipping_address = request.form.get('shipping_address', '').strip()
        public_note = request.form.get('public_note', '').strip()
        private_note = request.form.get('private_note', '').strip()
        foot_note = request.form.get('foot_note', '').strip()
        
        product_ids = request.form.getlist('item_product_id[]')
        item_codes = request.form.getlist('item_code[]')
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        prices = request.form.getlist('item_price[]')
        discounts = request.form.getlist('item_discount[]')
        
        if not customer_name or not product_ids:
            flash('Customer Name and at least one Product are required.', 'danger')
            return redirect(url_for('edit_invoice', invoice_id=invoice_id))
            
        # Get or Create Customer
        customer = db.customers.find_one({"name": {"$regex": f"^{re.escape(customer_name)}$", "$options": "i"}})
        if not customer:
            customer_doc = {
                "name": customer_name,
                "address": billing_address,
                "phone": "",
                "email": "",
                "created_at": datetime.utcnow()
            }
            res = db.customers.insert_one(customer_doc)
            customer = db.customers.find_one({"_id": res.inserted_id})
        else:
            if billing_address:
                db.customers.update_one({"_id": customer["_id"]}, {"$set": {"address": billing_address}})
                customer["address"] = billing_address
        
        items = []
        subtotal = 0.0
        
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            try:
                qty = int(quantities[i])
                price = float(prices[i])
            except (ValueError, IndexError):
                flash('Invalid quantity or price provided.', 'danger')
                return redirect(url_for('edit_invoice', invoice_id=invoice_id))
            
            code = item_codes[i] if i < len(item_codes) else ''
            desc = descriptions[i] if i < len(descriptions) else ''
            
            db_item = db.items.find_one({"_id": ObjectId(pid)})
            if not db_item:
                flash('One or more selected items does not exist.', 'danger')
                return redirect(url_for('edit_invoice', invoice_id=invoice_id))
                
            item_subtotal = qty * price
            discount_pct = float(discounts[i]) if i < len(discounts) else 0.0
            discount_amount = item_subtotal * (discount_pct / 100.0)
            item_after_discount = item_subtotal - discount_amount
            subtotal += item_after_discount
            
            items.append({
                "product_id": ObjectId(pid),
                "product_name": db_item.get('item_name', ''),
                "product_code": code,
                "description": desc,
                "quantity": qty,
                "price": price,
                "discount_pct": discount_pct,
                "discount_amount": discount_amount,
                "subtotal": item_after_discount
            })
                
        # Calculate Stock differences
        # 1. Add back old items quantities
        for old_item in invoice.get('items', []):
            if 'product_id' in old_item and old_item['product_id']:
                try:
                    db.items.update_one(
                        {"_id": old_item['product_id'], "manage_stock": True},
                        {"$inc": {"current_qty": old_item.get('quantity', 0)}}
                    )
                except Exception:
                    pass
        # 2. Deduct new items quantities
        for new_item in items:
            if 'product_id' in new_item and new_item['product_id']:
                try:
                    db.items.update_one(
                        {"_id": new_item['product_id'], "manage_stock": True},
                        {"$inc": {"current_qty": -new_item.get('quantity', 0)}}
                    )
                except Exception:
                    pass
                
        tax_amount = subtotal * (tax_rate / 100.0)
        grand_total = subtotal + tax_amount
        amount_paid_str = request.form.get('amount_paid', '0').strip()
        amount_paid = float(amount_paid_str) if amount_paid_str else 0.0
        balance_due = max(0.0, grand_total - amount_paid)
        
        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d') if invoice_date_str else datetime.utcnow()
        try:
            payment_days_int = int(payment_days) if payment_days else 30
        except ValueError:
            payment_days_int = 30
        due_date = invoice_date + timedelta(days=payment_days_int)
        
        update_doc = {
            "invoice_date": invoice_date,
            "due_date": due_date,
            "payment_terms": payment_terms,
            "payment_days": payment_days,
            "po_number": po_number,
            "salesperson": salesperson,
            "shipping_address": shipping_address,
            "public_note": public_note,
            "private_note": private_note,
            "foot_note": foot_note,
            "customer": {
                "customer_id": customer['_id'],
                "name": customer['name'],
                "phone": customer.get('phone', ''),
                "email": customer.get('email', ''),
                "address": customer.get('address', '')
            },
            "items": items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "grand_total": grand_total,
            "amount_paid": amount_paid,
            "balance_due": balance_due,
            "updated_at": datetime.utcnow()
        }
        
        db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": update_doc})
        flash(f'Invoice {invoice.get("invoice_number", "")} updated successfully!', 'success')
        return redirect(url_for('download_invoice_pdf', invoice_id=invoice_id))
        
    # GET Method - render create invoice with prefilled data
    customers_list = list(db.customers.find().sort("name", 1))
    items_list = list(db.items.find().sort("item_code", 1))
    
    items_json = json.dumps([
        {
            "id": str(item['_id']),
            "name": item.get('item_name', ''),
            "code": item.get('item_code', ''),
            "description": item.get('description', ''),
            "price": item.get('price', 0),
            "stock": item.get('current_qty', 0) if item.get('manage_stock') else -1
        }
        for item in items_list
    ])
    
    customers_json = json.dumps({
        cust['name']: {
            "address": cust.get('address', '').replace('\n', ' '),
            "phone": cust.get('phone', ''),
            "email": cust.get('email', '')
        }
        for cust in customers_list
    })
    
    def serialize_invoice(inv):
        inv_copy = dict(inv)
        inv_copy['_id'] = str(inv_copy['_id'])
        if 'customer' in inv_copy and 'customer_id' in inv_copy['customer']:
            inv_copy['customer']['customer_id'] = str(inv_copy['customer']['customer_id'])
        if 'invoice_date' in inv_copy:
            inv_copy['invoice_date'] = inv_copy['invoice_date'].strftime('%Y-%m-%d')
        if 'due_date' in inv_copy:
            inv_copy['due_date'] = inv_copy['due_date'].strftime('%Y-%m-%d')
        if 'created_at' in inv_copy:
            inv_copy['created_at'] = inv_copy['created_at'].strftime('%Y-%m-%dT%H:%M:%S')
        if 'updated_at' in inv_copy:
            inv_copy['updated_at'] = inv_copy['updated_at'].strftime('%Y-%m-%dT%H:%M:%S')
        for item in inv_copy.get('items', []):
            if 'product_id' in item:
                item['product_id'] = str(item['product_id'])
        return json.dumps(inv_copy)
        
    edit_invoice_json = serialize_invoice(invoice)
    today_str = invoice.get('invoice_date', datetime.utcnow()).strftime('%Y-%m-%d')
    suggested_invoice_num = invoice.get('invoice_number', '')
    
    return render_template('invoice_create.html', customers=customers_list, items=items_list, 
                           items_json=items_json, customers_json=customers_json, 
                           today=today_str, suggested_invoice_num=suggested_invoice_num,
                           edit_invoice_json=edit_invoice_json, edit_mode=True, invoice_id=invoice_id)

# ==========================================
# REPORTS ROUTE & EXPORTS
# ==========================================
@app.route('/reports')
@login_required
def reports():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    
    # Default range: last 30 days if not set
    if not start_date_str:
        start_date = datetime.utcnow() - timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
    if not end_date_str:
        end_date = datetime.utcnow()
        end_date_str = end_date.strftime('%Y-%m-%d')
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
    # Match query for dates
    match_query = {
        "invoice_date": {
            "$gte": start_date,
            "$lte": end_date + timedelta(days=1)
        }
    }
    
    # 1. Total Revenue in date range
    revenue_agg = list(db.invoices.aggregate([
        {"$match": match_query},
        {"$group": {"_id": None, "subtotal": {"$sum": "$subtotal"}, "tax": {"$sum": "$tax_amount"}, "total": {"$sum": "$grand_total"}}}
    ]))
    
    totals = revenue_agg[0] if revenue_agg else {"subtotal": 0.0, "tax": 0.0, "total": 0.0}
    
    # 2. Top Selling Products
    top_products = list(db.invoices.aggregate([
        {"$match": match_query},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_name",
            "code": {"$first": "$items.product_code"},
            "units_sold": {"$sum": "$items.quantity"},
            "revenue": {"$sum": "$items.subtotal"}
        }},
        {"$sort": {"units_sold": -1}},
        {"$limit": 5}
    ]))
    
    # 3. Customer Purchase Report
    customer_report = list(db.invoices.aggregate([
        {"$match": match_query},
        {"$group": {
            "_id": "$customer.customer_id",
            "name": {"$first": "$customer.name"},
            "phone": {"$first": "$customer.phone"},
            "invoice_count": {"$sum": 1},
            "total_spent": {"$sum": "$grand_total"}
        }},
        {"$sort": {"total_spent": -1}},
        {"$limit": 10}
    ]))
    
    # 4. Daily Sales breakdown for list/table
    daily_sales = list(db.invoices.aggregate([
        {"$match": match_query},
        {"$group": {
            "_id": { "$dateToString": { "format": "%Y-%m-%d", "date": "$invoice_date" } },
            "count": {"$sum": 1},
            "revenue": {"$sum": "$grand_total"}
        }},
        {"$sort": {"_id": -1}}
    ]))
    
    return render_template('reports.html', 
                           totals=totals, 
                           top_products=top_products,
                           customer_report=customer_report, 
                           daily_sales=daily_sales,
                           start_date=start_date_str, 
                           end_date=end_date_str)

@app.route('/reports/export')
@login_required
def export_report():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    
    query = {}
    if start_date_str or end_date_str:
        date_query = {}
        if start_date_str:
            date_query["$gte"] = datetime.strptime(start_date_str, '%Y-%m-%d')
        if end_date_str:
            date_query["$lte"] = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        query["invoice_date"] = date_query
        
    invoices_list = list(db.invoices.find(query).sort("invoice_date", 1))
    
    # Write to a string-based CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Invoice Number', 'Invoice Date', 'Customer Name', 'Customer Phone', 'Subtotal', 'Tax Amount', 'Grand Total'])
    
    for inv in invoices_list:
        cw.writerow([
            inv['invoice_number'],
            inv['invoice_date'].strftime('%Y-%m-%d'),
            inv['customer']['name'],
            inv['customer']['phone'],
            f"{inv['subtotal']:.2f}",
            f"{inv['tax_amount']:.2f}",
            f"{inv['grand_total']:.2f}"
        ])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=sales_report_{start_date_str}_to_{end_date_str}.csv"}
    )

# ==========================================
# ITEM MANAGEMENT ROUTES
# ==========================================
@app.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'POST':
        action = request.form.get('action')
        item_code = request.form.get('item_code', '').strip().upper()
        item_name = request.form.get('item_name', '').strip()
        description = request.form.get('description', '').strip()
        quantity = request.form.get('quantity', '').strip()
        
        # Parse price - handle currency symbol prefix
        price_str = request.form.get('price', '0').strip().replace('₹', '').replace(',', '')
        try:
            price = float(price_str) if price_str else 0
        except ValueError:
            price = 0
        
        tax = request.form.get('tax', '').strip()
        manage_stock = request.form.get('manage_stock') == '1'
        current_qty = int(request.form.get('current_qty', 0) or 0)
        ideal_qty = int(request.form.get('ideal_qty', 0) or 0)
        warning_qty = int(request.form.get('warning_qty', 0) or 0)
        supplier = request.form.get('supplier', '').strip()
        note = request.form.get('note', '').strip()
        
        # Use item_code as item_name if item_name is empty
        if not item_name:
            item_name = item_code
        
        if not item_code or price <= 0:
            flash('Item Code and valid Price are required.', 'danger')
            return redirect(url_for('items'))
        
        if action == 'add':
            if db.items.find_one({"item_code": item_code}):
                flash(f'Item Code "{item_code}" already exists.', 'danger')
                return redirect(url_for('items'))
            
            db.items.insert_one({
                "item_code": item_code,
                "item_name": item_name,
                "description": description,
                "quantity": quantity,
                "price": price,
                "tax": tax,
                "manage_stock": manage_stock,
                "current_qty": current_qty,
                "ideal_qty": ideal_qty,
                "warning_qty": warning_qty,
                "supplier": supplier,
                "note": note,
                "created_at": datetime.utcnow()
            })
            flash('Item added successfully!', 'success')
        
        elif action == 'edit':
            item_id = request.form.get('item_id')
            if item_id:
                try:
                    # Check duplicate code excluding current
                    existing = db.items.find_one({"item_code": item_code, "_id": {"$ne": ObjectId(item_id)}})
                    if existing:
                        flash(f'Item Code "{item_code}" already exists.', 'danger')
                        return redirect(url_for('items'))
                    
                    db.items.update_one(
                        {"_id": ObjectId(item_id)},
                        {"$set": {
                            "item_code": item_code,
                            "item_name": item_name,
                            "description": description,
                            "quantity": quantity,
                            "price": price,
                            "tax": tax,
                            "manage_stock": manage_stock,
                            "current_qty": current_qty,
                            "ideal_qty": ideal_qty,
                            "warning_qty": warning_qty,
                            "supplier": supplier,
                            "note": note
                        }}
                    )
                    flash('Item updated successfully!', 'success')
                except Exception as e:
                    flash('Error updating item.', 'danger')
        
        return redirect(url_for('items'))
    
    search_query = request.args.get('search', '').strip()
    if search_query:
        # Fix #12: Escape user input to prevent ReDoS vulnerability
        rgx = re.compile(re.escape(search_query), re.IGNORECASE)
        item_list = list(db.items.find({
            "$or": [{"item_name": rgx}, {"item_code": rgx}, {"description": rgx}]
        }).sort("item_code", 1))
    else:
        item_list = list(db.items.find().sort("item_code", 1))
    
    return render_template('items.html', items=item_list, search_query=search_query)

@app.route('/items/delete/<item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    try:
        db.items.delete_one({"_id": ObjectId(item_id)})
        flash('Item deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting item.', 'danger')
    return redirect(url_for('items'))

@app.route('/api/item/<item_code>', methods=['GET'])
@login_required
def get_item(item_code):
    try:
        item = db.items.find_one({"item_code": item_code.upper()})
        if item:
            return jsonify({
                "_id": str(item['_id']),
                "item_code": item['item_code'],
                "item_name": item['item_name'],
                "quantity": item['quantity'],
                "price": item['price']
            })
        else:
            return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# PDF GENERATION ROUTE
# ==========================================
@app.route('/invoices/<invoice_id>/download-pdf', methods=['GET'])
@login_required
def download_invoice_pdf(invoice_id):
    try:
        invoice = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except Exception:
        invoice = None
    
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices'))
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib import colors
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=1.5*inch, leftMargin=0.6*inch, rightMargin=0.6*inch)
        elements = []

        def draw_page_border(canvas, doc_obj):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor('#d32f2f'))
            canvas.setLineWidth(1.5)
            # Outer red border
            canvas.rect(doc_obj.leftMargin - 0.2 * inch, 0.3 * inch,
                        A4[0] - doc_obj.leftMargin - doc_obj.rightMargin + 0.4 * inch,
                        A4[1] - 0.6 * inch,
                        stroke=1, fill=0)
            
            # Dotted footer line
            canvas.setDash(2, 2)
            dotted_y = doc_obj.bottomMargin - 0.1 * inch
            canvas.line(doc_obj.leftMargin, dotted_y,
                        A4[0] - doc_obj.rightMargin, dotted_y)
            
            # Draw footer table
            footer_table.wrapOn(canvas, A4[0] - doc_obj.leftMargin - doc_obj.rightMargin, doc_obj.bottomMargin)
            footer_table.drawOn(canvas, doc_obj.leftMargin, 0.4 * inch)
            
            canvas.restoreState()
        
        styles = getSampleStyleSheet()
        
        # ---- CONSTANT BUSINESS INFO ----
        BUSINESS_NAME = "red studio"
        BUSINESS_ADDRESS = "1st Floor, tea point, 1/200 A, Red Studio, Madurai - Rameswaram<br/>Hwy, Ramanathapuram, Achundanvayal, Tamil Nadu 623502"
        
        # ---- LOGO ----
        logo_path = os.path.join(app.root_path, 'static', 'uploads', 'logo.jpg')
        # Fallback: check for the root-level logo
        if not os.path.exists(logo_path):
            logo_path = os.path.join(app.root_path, 'logo.jpg (1).jpeg')
        
        # Company Header with Logo + Invoice badge
        company_style = ParagraphStyle(
            'CompanyHeader',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        )
        
        address_style = ParagraphStyle(
            'Address',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#333333'),
            spaceAfter=4,
            leading=11
        )
        
        invoice_badge_style = ParagraphStyle(
            'InvoiceBadge',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            alignment=2
        )
        
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            alignment=2,
            spaceAfter=2
        )
        
        # Build header: Logo on left, Invoice badge + date on right
        # Left column: logo + company name + address
        left_elements = []
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=1.3*inch, height=0.8*inch)
                logo_img.hAlign = 'LEFT'
                left_elements.append(logo_img)
            except Exception:
                pass
        
        left_elements.append(Paragraph(f"<b>{BUSINESS_NAME}</b>", company_style))
        left_elements.append(Paragraph(BUSINESS_ADDRESS, address_style))
        
        # Right column: Invoice badge + details
        from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon, Path
        def get_slashes():
            d = Drawing(40, 30)
            for i in range(3):
                p = Path(fillColor=colors.HexColor('#d32f2f'), strokeColor=None)
                p.moveTo(5 + i*8, 0); p.lineTo(9 + i*8, 0); p.lineTo(17 + i*8, 30); p.lineTo(13 + i*8, 30); p.closePath()
                d.add(p)
            return d

        right_elements = []
        inv_badge = Table([[get_slashes(), Paragraph('<font color="white"><b>INVOICE</b></font>', ParagraphStyle('InvT', parent=styles['Normal'], fontSize=18, alignment=1))]], colWidths=[0.6*inch, 2.2*inch])
        inv_badge.setStyle(TableStyle([('BACKGROUND', (1,0), (1,0), colors.HexColor('#d32f2f')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('RIGHTPADDING', (0,0), (-1,-1), 0), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
        inv_badge.hAlign = 'RIGHT'
        
        right_elements.append(inv_badge)
        right_elements.append(Spacer(1, 15))
        
        due_date = invoice['invoice_date'] + timedelta(days=int(invoice.get('payment_days', 30) or 30))
        meta_data = [
            ["Date", ":", invoice['invoice_date'].strftime('%d %b %Y')],
            ["Invoice No.", ":", str(invoice['invoice_number'])],
            ["Due Date", ":", due_date.strftime('%d %b %Y')]
        ]
        meta_table = Table(meta_data, colWidths=[0.9*inch, 0.2*inch, 1.7*inch])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTNAME', (0,0), (1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2)
        ]))
        meta_table.hAlign = 'RIGHT'
        
        right_elements.append(meta_table)
        
        # Create a header table with left and right columns
        from reportlab.platypus import KeepTogether
        
        left_cell = []
        for el in left_elements:
            left_cell.append(el)
        
        right_cell = []
        for el in right_elements:
            right_cell.append(el)
        
        header_table = Table(
            [[left_cell, right_cell]],
            colWidths=[4.0*inch, 2.8*inch]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        header_table.hAlign = 'LEFT'
        elements.append(header_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # Bill To section
        def get_user_icon():
            d = Drawing(30, 30)
            d.add(Circle(15, 15, 15, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            d.add(Circle(15, 19, 4.5, fillColor=colors.white, strokeColor=None))
            p = Path(fillColor=colors.white, strokeColor=None)
            p.moveTo(15, 13); p.lineTo(9, 13); p.lineTo(7, 7); p.lineTo(7, 5); p.lineTo(23, 5); p.lineTo(23, 7); p.lineTo(21, 13); p.closePath()
            d.add(p)
            return d

        bill_to_header_style = ParagraphStyle('BillToHeader', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#d32f2f'), spaceAfter=4)
        bill_to_name_style = ParagraphStyle('BillToName', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.black, spaceAfter=2)
        bill_to_style = ParagraphStyle('BillTo', parent=styles['Normal'], fontSize=9, textColor=colors.black, leading=12)
        
        bill_info = []
        bill_info.append([Paragraph("<b>BILL TO</b>", bill_to_header_style)])
        bill_info.append([Paragraph(invoice['customer']['name'], bill_to_name_style)])
        if invoice['customer'].get('phone'):
            bill_info.append([Paragraph(f"Phone: {invoice['customer']['phone']}", bill_to_style)])
        
        bill_info_table = Table(bill_info, colWidths=[3.5*inch])
        bill_info_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0), ('TOPPADDING', (0,0), (-1,-1), 0)]))
        
        bill_section = Table([[get_user_icon(), bill_info_table]], colWidths=[0.5*inch, 3.5*inch])
        bill_section.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
        bill_section.hAlign = 'LEFT'
        elements.append(bill_section)
        elements.append(Spacer(1, 0.2*inch))
        
        # Items table - matching the reference screenshot style
        items_header_style = ParagraphStyle('ItemHeader', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', textColor=colors.white)
        items_cell_style = ParagraphStyle('ItemCell', parent=styles['Normal'], fontSize=8, textColor=colors.black)
        
        items_data = [[
            Paragraph("Qty", items_header_style),
            Paragraph("Description", items_header_style),
            Paragraph("Unit Price", items_header_style),
            Paragraph("Discount", items_header_style),
            Paragraph("Total", items_header_style)
        ]]
        for item in invoice['items']:
            disc_pct = item.get('discount_pct', 0)
            disc_display = f"{disc_pct:.1f}%" if disc_pct else "-"
            items_data.append([
                Paragraph(str(item['quantity']), items_cell_style),
                # Show description from the items collection
                Paragraph(f"{item.get('description') or item.get('product_name')} [ {item.get('product_code', '')} ]", items_cell_style),
                Paragraph(f"Rs.{item['price']:,.2f}", ParagraphStyle('Price', parent=items_cell_style, alignment=2)),
                Paragraph(disc_display, ParagraphStyle('Disc', parent=items_cell_style, alignment=1)),
                Paragraph(f"Rs.{item['subtotal']:,.2f}", ParagraphStyle('Total', parent=items_cell_style, alignment=2))
            ])
        
        # Add empty rows for visual spacing (like the reference)
        for _ in range(max(0, 4 - len(invoice['items']))):
            items_data.append(['', '', '', '', ''])
        
        items_table = Table(items_data, colWidths=[0.6*inch, 2.8*inch, 1.2*inch, 0.9*inch, 1.3*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        items_table.hAlign = 'LEFT'
        elements.append(items_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Totals - right aligned matching reference
        total_label_style = ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=0)
        total_value_style = ParagraphStyle('TotalValue', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=2)
        
        # Calculate total discount for display
        total_discount = sum(item.get('discount_amount', 0) for item in invoice['items'])
        
        totals_data = []
        if total_discount > 0:
            totals_data.append(
                ['', '', '', Paragraph('<b>Discount</b>', ParagraphStyle('DiscLabel', parent=total_label_style, textColor=colors.HexColor('#d32f2f'))), Paragraph(f'<b>- Rs.{total_discount:,.2f}</b>', ParagraphStyle('DiscVal', parent=total_value_style, textColor=colors.HexColor('#d32f2f')))]
            )
            
        totals_data.append(
            ['', '', '', Paragraph("<b>Total</b>", total_label_style), Paragraph(f"<b>Rs.{invoice['grand_total']:,.2f}</b>", total_value_style)]
        )
        
        totals_table = Table(totals_data, colWidths=[0.6*inch, 2.8*inch, 1.2*inch, 0.9*inch, 1.3*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (3, 0), (4, -1), 'RIGHT'),
            ('FONTNAME', (3, 0), (4, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LINEBELOW', (3, -1), (4, -1), 1.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        totals_table.hAlign = 'LEFT'
        elements.append(totals_table)
        elements.append(Spacer(1, 0.2*inch))
        
        amount_paid = float(invoice.get('amount_paid', 0.0))
        balance_due = float(invoice.get('balance_due', invoice['grand_total']))
        
        # Payments block
        if amount_paid > 0 and balance_due > 0:
            payment_header_style = ParagraphStyle('PayHdr', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#d32f2f'), alignment=1)
            payment_date_style = ParagraphStyle('PayDate', parent=styles['Normal'], fontSize=9, textColor=colors.black, alignment=1)
            payment_txt_style = ParagraphStyle('PayTxt', parent=styles['Normal'], fontSize=9, textColor=colors.black, alignment=1)
            payment_amt_style = ParagraphStyle('PayAmt', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#d32f2f'), alignment=2)
            payment_thx_style = ParagraphStyle('PayThx', parent=styles['Normal'], fontSize=8, textColor=colors.black, alignment=1)
            
            pay_date_str = invoice['invoice_date'].strftime('%d %b %Y') # assuming paid on invoice date if no separate date is stored
            
            pay_data = [
                [Paragraph("<b>PAYMENTS</b>", payment_header_style)],
                [
                    Table([[
                        Paragraph(pay_date_str, payment_date_style),
                        Paragraph("Payment Received", payment_txt_style),
                        Paragraph(f"- Rs.{amount_paid:,.2f}", payment_amt_style)
                    ]], colWidths=[1.2*inch, 2.0*inch, 1.5*inch])
                ],
                [Paragraph("( Thank you for your payment )", payment_thx_style)]
            ]
            
            pay_table = Table(pay_data, colWidths=[4.7*inch])
            pay_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d32f2f')),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#fdeeee')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#d32f2f')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 8),
            ]))
            
            # Right align the payment table (relative to full width)
            wrapper_data = [['', pay_table]]
            wrapper_table = Table(wrapper_data, colWidths=[2.1*inch, 4.7*inch])
            wrapper_table.hAlign = 'LEFT'
            elements.append(wrapper_table)
            elements.append(Spacer(1, 0.1*inch))
        
        # Balance Due block
        if balance_due > 0:
            bal_label = ParagraphStyle('BalLbl', parent=styles['Normal'], fontSize=14, fontName='Helvetica-Bold', textColor=colors.HexColor('#d32f2f'))
            bal_val = ParagraphStyle('BalVal', parent=styles['Normal'], fontSize=16, fontName='Helvetica-Bold', textColor=colors.HexColor('#d32f2f'), alignment=2)
            
            bal_data = [
                [Paragraph("<b>BALANCE DUE</b>", bal_label), Paragraph(f"<b>Rs.{balance_due:,.2f}</b>", bal_val)]
            ]
            bal_table = Table(bal_data, colWidths=[2.35*inch, 2.35*inch])
            bal_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d32f2f')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fdeeee')),
                ('ALIGN', (0,0), (0,0), 'LEFT'),
                ('ALIGN', (1,0), (1,0), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 12),
            ]))
            
            wrapper_data = [['', bal_table]]
            wrapper_table = Table(wrapper_data, colWidths=[2.1*inch, 4.7*inch])
            wrapper_table.hAlign = 'LEFT'
            elements.append(wrapper_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Footer - Thank you note
        def get_doc_icon():
            d = Drawing(30, 30)
            d.add(Circle(15, 15, 14, fillColor=colors.white, strokeColor=colors.HexColor('#d32f2f'), strokeWidth=1.5))
            d.add(Rect(10, 8, 10, 14, fillColor=None, strokeColor=colors.HexColor('#d32f2f'), strokeWidth=1.2))
            d.add(Rect(12, 17, 6, 1, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            d.add(Rect(12, 14, 6, 1, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            d.add(Rect(12, 11, 4, 1, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            return d

        def get_phone_icon():
            d = Drawing(16, 16)
            d.add(Circle(8, 8, 8, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            p = Path(fillColor=colors.white, strokeColor=None)
            p.moveTo(5, 11); p.curveTo(4, 11, 4, 9, 5, 8); p.lineTo(8, 5); p.curveTo(9, 4, 11, 4, 11, 5)
            p.lineTo(12, 6); p.curveTo(12, 7, 10, 8, 9, 7); p.lineTo(7, 9); p.curveTo(8, 10, 7, 12, 6, 12); p.lineTo(5, 11); p.closePath()
            d.add(p)
            return d

        def get_marker_icon():
            d = Drawing(16, 16)
            d.add(Circle(8, 8, 8, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            p = Path(fillColor=colors.white, strokeColor=None)
            p.moveTo(8, 3); p.lineTo(5, 8); p.curveTo(5, 11, 11, 11, 11, 8); p.lineTo(8, 3); p.closePath()
            d.add(p)
            d.add(Circle(8, 8.5, 1.5, fillColor=colors.HexColor('#d32f2f'), strokeColor=None))
            return d

        thank_you_style_red = ParagraphStyle('ThxRed', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#d32f2f'))
        thank_you_style_blk = ParagraphStyle('ThxBlk', parent=styles['Normal'], fontSize=9, textColor=colors.black)
        
        elements.append(Spacer(1, 0.3*inch))
        
        thx_info = []
        thx_info.append([Paragraph("<b>Thank you for your business.</b>", thank_you_style_red)])
        thx_info.append([Paragraph("If you have any questions, please feel free to contact us.", thank_you_style_blk)])
        thx_table = Table(thx_info)
        thx_table.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2)]))
        
        thx_section = Table([[get_doc_icon(), thx_table]], colWidths=[0.5*inch, 4*inch])
        thx_section.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
        thx_section.hAlign = 'LEFT'
        elements.append(thx_section)
        
        # Footer table is now drawn in draw_page_border
        phone_style = ParagraphStyle('PhoneSt', parent=styles['Normal'], fontSize=9, textColor=colors.black)
        
        footer_info = [
            [get_phone_icon(), Paragraph(f"Phone: {BUSINESS_NAME.replace('red studio', '8870650403')}", phone_style)],
            [get_marker_icon(), Paragraph(f"Address: {BUSINESS_ADDRESS.replace('<br/>', ' ')}", phone_style)]
        ]
        footer_table = Table(footer_info, colWidths=[0.3*inch, 6*inch])
        footer_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 4), ('TOPPADDING', (0,0), (-1,-1), 4)]))
        footer_table.hAlign = 'LEFT'
        # Do not append footer_table to elements, it is drawn in draw_page_border
        
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=1.4*inch, leftMargin=0.6*inch, rightMargin=0.6*inch)
        doc.build(elements, onFirstPage=draw_page_border, onLaterPages=draw_page_border)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Invoice_{invoice['invoice_number']}.pdf"
        )

    
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'danger')
        return redirect(url_for('invoice_view', invoice_id=invoice_id))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    settings_doc = db.settings.find_one({})
    
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        gst_number = request.form.get('gst_number', '').strip()
        
        if not business_name:
            flash('Business Name is required.', 'danger')
            return redirect(url_for('settings'))
            
        logo_path = settings_doc.get('logo_path', '') if settings_doc else ''
        
        # Handle file upload for business logo
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # save with timestamp to avoid caching issues
                ext = os.path.splitext(filename)[1]
                filename = f"logo_{int(datetime.utcnow().timestamp())}{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                logo_path = f"/static/uploads/{filename}"
                
        update_data = {
            "business_name": business_name,
            "logo_path": logo_path,
            "address": address,
            "phone": phone,
            "email": email,
            "gst_number": gst_number
        }
        
        if settings_doc:
            db.settings.update_one({"_id": settings_doc['_id']}, {"$set": update_data})
        else:
            db.settings.insert_one(update_data)
            
        flash('Business settings updated successfully!', 'success')
        return redirect(url_for('settings'))
        
    return render_template('settings.html', settings=settings_doc)

if __name__ == '__main__':
    # Initialize port and debug modes
    app.run(host='0.0.0.0', port=5000, debug=True)
