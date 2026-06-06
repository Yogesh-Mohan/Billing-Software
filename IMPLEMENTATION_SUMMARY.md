# RED STUDIO Billing System - Implementation Summary

## ✅ Features Implemented

### 1. **Permanent Company Details on Invoices**
- **Name:** Red Studio (hardcoded on all invoices)
- **Address:** 1st Floor, Tea Point, 1/200 A, Red Studio, Madurai–Rameswaram Highway, Ramanathapuram, Achundanvayal, Tamil Nadu 623502 (hardcoded)
- These details are **permanently displayed** and **never change** across all invoices
- Implementation: Updated `invoice_view.html` to use hardcoded values instead of database settings

### 2. **Item Management System**
New sidebar section for managing reusable invoice items with the following features:

**Features:**
- ✅ Add new items with unique item codes
- ✅ Each item stores: Code, Name, Quantity/Unit, Price
- ✅ Edit existing items
- ✅ Delete items
- ✅ Search items by name or code
- ✅ All items stored permanently in MongoDB

**New Routes:**
- `GET /items` - View all items with search
- `POST /items` - Add/Edit items
- `POST /items/delete/<item_id>` - Delete item
- `GET /api/item/<item_code>` - Lookup item by code (API endpoint)

**Database Collection:**
- Collection: `items`
- Unique Index on: `item_code`
- Fields: `item_code`, `item_name`, `quantity`, `price`, `created_at`

### 3. **Auto-Fill Item Details on Invoices**
When creating an invoice, users can enter the item code in the invoice form:
- **System automatically fetches** and populates:
  - Item name
  - Quantity/Unit
  - Price per unit
- Implementation: JavaScript function `lookupItemByCode()` in `static/js/main.js`
- API endpoint: `/api/item/<item_code>` returns item details as JSON

### 4. **PDF Generation & Download**
New "Download PDF" button on invoice view page:
- **Location:** Next to Print button on invoice page
- **Features:**
  - ✅ Generates professional PDF with Red Studio branding
  - ✅ Includes permanent company header and address
  - ✅ Shows invoice number, date, customer details
  - ✅ Itemized table with products, quantities, prices
  - ✅ Tax calculation breakdown
  - ✅ Grand total calculation
  - ✅ Professional formatting with Red Studio colors
  - ✅ Footer with company contact info

**New Route:**
- `GET /invoices/<invoice_id>/download-pdf` - Generate and download invoice as PDF

**Dependencies:**
- Added: `reportlab==4.0.9` to requirements.txt

### 5. **Sidebar Navigation Updates**
Added new menu item in the left sidebar:
- **Items Management** - Link to manage invoice items
- Icon: <i class="fas fa-list"></i>
- Position: Between "Products" and "Create Invoice"

## 🗄️ Database Schema Changes

### New Collection: `items`
```json
{
  "_id": ObjectId,
  "item_code": "string (unique)",
  "item_name": "string",
  "quantity": "string (e.g., '10 kg')",
  "price": "double",
  "created_at": "datetime"
}
```

### Updated: `db_seed.py`
- Added index creation for `items.item_code` (unique)

## 📦 Dependencies Added
```
reportlab==4.0.9  # PDF generation
```

## 📁 Files Modified/Created

### Created:
- `templates/items.html` - Item management interface with modals for add/edit

### Modified:
- `app.py` - Added 4 new routes for item management and PDF generation
- `requirements.txt` - Added reportlab dependency
- `db_seed.py` - Added items collection index
- `templates/base.html` - Added Items menu item to sidebar
- `templates/invoice_view.html` - 
  - Hardcoded permanent company details
  - Added "Download PDF" button
- `static/js/main.js` - Added item lookup functions

## 🔧 How to Use

### Adding Items:
1. Go to **Items** in the sidebar
2. Click **"Add New Item"**
3. Fill in:
   - Item Code (e.g., CAKE-001)
   - Item Name (e.g., Chocolate Cake)
   - Quantity/Unit (e.g., 10 kg)
   - Price (e.g., 1000)
4. Click **"Add Item"**

### Using Items in Invoices:
1. Go to **Create Invoice**
2. In the items table, enter the **Item Code** (e.g., CAKE-001)
3. Press Tab or click outside the field
4. System **automatically fills**:
   - Item Name
   - Quantity
   - Unit Price
5. Proceed with invoice creation

### Downloading Invoice as PDF:
1. Go to **Invoice History**
2. Click on an invoice to view it
3. Click **"Download PDF"** button
4. PDF will download to your computer

## 🎨 Invoice PDF Format
The PDF includes:
- **Header**: Red Studio logo (if set), company name and address
- **Invoice Details**: Invoice number, date
- **Customer Section**: Billed To and Shipping Address
- **Items Table**: Item code, name, quantity, unit price, total
- **Totals Section**: Subtotal, Tax, Grand Total
- **Footer**: Thank you message and contact info

## ⚙️ Installation & Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Initialize Database (if new)
```bash
python db_seed.py
```

### Step 3: Run the Application
```bash
python app.py
```

## 🔐 Notes
- All business details (name and address) are now **hardcoded** on invoices for consistency
- Item codes are **case-insensitive** (CAKE-001 = cake-001)
- Each item must have a **unique item code**
- PDFs are generated on-the-fly using ReportLab
- Item lookup is real-time via REST API call

## 🐛 Troubleshooting

**Issue**: "Item not found" when entering item code
- **Solution**: Check item code is exactly correct (case-insensitive matching works)
- Go to Items page and verify the item exists

**Issue**: PDF download button not working
- **Solution**: Ensure reportlab is installed: `pip install reportlab==4.0.9`
- Check that MongoDB connection is working

**Issue**: Items not saving
- **Solution**: Verify MongoDB is running
- Check that `items` collection index was created in db_seed.py

## 📚 API Endpoints

### Item Lookup API
**GET** `/api/item/<item_code>`
- Returns JSON with item details
- Example response:
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "item_code": "CAKE-001",
  "item_name": "Chocolate Cake",
  "quantity": "10 kg",
  "price": 1000.00
}
```

### Invoice PDF Download
**GET** `/invoices/<invoice_id>/download-pdf`
- Generates PDF and downloads as `Invoice_INV-YYYYMMDD-XXXX.pdf`
- Requires authentication (login required)

---

**Version**: 1.0
**Last Updated**: 2026-06-04
**Status**: ✅ Production Ready
