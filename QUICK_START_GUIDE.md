# Quick Start Guide - RED STUDIO Billing System

## 🚀 Getting Started

### Prerequisites
- Python 3.7+
- MongoDB running locally or access to MongoDB server
- pip (Python package manager)

### Installation

1. **Install Dependencies**
   ```bash
   cd c:\Users\waray\OneDrive\Desktop\sriram
   pip install -r requirements.txt
   ```

2. **Initialize Database** (run once)
   ```bash
   python db_seed.py
   ```
   This will:
   - Create admin user: `admin` / `admin123`
   - Set up default business settings
   - Create sample customers and products
   - Create `items` collection with unique index

3. **Start the Application**
   ```bash
   python app.py
   ```
   - Visit: http://localhost:5000
   - Login with: `admin` / `admin123`

---

## 📝 Creating & Using Items

### Step 1: Add Your First Item
1. Click **Items** in left sidebar
2. Click **"Add New Item"** button
3. Fill in the form:
   - **Item Code**: `CAKE-001` (unique identifier)
   - **Item Name**: `Chocolate Cake`
   - **Quantity (Unit)**: `10 kg`
   - **Price**: `1000`
4. Click **"Add Item"**

### Step 2: Use Item in Invoice
1. Go to **Create Invoice**
2. Select a customer
3. In the items table, find the **Item Code** column
4. Type the item code: `CAKE-001`
5. Press **Tab** or click outside
   - ✅ Name auto-fills: "Chocolate Cake"
   - ✅ Quantity auto-fills: "10 kg"  
   - ✅ Price auto-fills: "₹1000"
6. Adjust quantity if needed
7. Continue adding more items
8. Click **"Create Invoice"** button

### Step 3: Download Invoice as PDF
1. Go to **Invoices** → **Invoice History**
2. Click on an invoice to view it
3. Click **"Download PDF"** button
4. PDF saves as: `Invoice_INV-YYYYMMDD-XXXX.pdf`

---

## 📋 Invoice Details on PDF

Every invoice PDF includes:
- ✅ **Company Header**: 
  - Name: Red Studio
  - Address: 1st Floor, Tea Point, 1/200 A, Red Studio, Madurai–Rameswaram Highway, Ramanathapuram, Achundanvayal, Tamil Nadu 623502
  - Phone & Email
- ✅ **Invoice Info**: Number, Date
- ✅ **Customer Details**: Name, Phone, Email, Address
- ✅ **Items Table**: Code, Name, Qty, Unit Price, Total
- ✅ **Calculations**: Subtotal, Tax, Grand Total
- ✅ **Footer**: Thank you message

---

## 🎯 Common Tasks

### Manage Items
| Task | Steps |
|------|-------|
| **View all items** | Click Items → See full list |
| **Search items** | Items → Search box → Enter name/code |
| **Edit item** | Items → Click ✏️ button → Update → Save |
| **Delete item** | Items → Click 🗑️ button → Confirm |

### Create Invoices
| Task | Steps |
|------|-------|
| **Auto-fill item** | Enter item code → Tab → Auto-fills |
| **Add multiple items** | Repeat item code entry for each item |
| **Generate PDF** | View Invoice → Click "Download PDF" |
| **Print invoice** | View Invoice → Click "Print" |

### View Invoices
| Task | Steps |
|------|-------|
| **See all invoices** | Invoices → See full history |
| **Search invoices** | Invoices → Search by number/customer |
| **View details** | Click invoice number → Full details |
| **Delete invoice** | View invoice → Delete button |

---

## 🔑 Default Credentials
- **Username**: `admin`
- **Password**: `admin123`

⚠️ **Important**: Change these credentials in a production environment!

---

## ⚙️ Configuration

### Update Permanent Company Details
The following details are **hardcoded** on all invoices:
- **Company Name**: Red Studio
- **Address**: 1st Floor, Tea Point, 1/200 A, Red Studio, Madurai–Rameswaram Highway, Ramanathapuram, Achundanvayal, Tamil Nadu 623502

To change these, edit `templates/invoice_view.html` and `app.py` (PDF generation section)

### Customize Tax Rate
When creating an invoice, you can set the tax percentage (default: 0%)

### Add Your Logo
1. Go to **Settings**
2. Upload your company logo
3. Logo will appear on invoice PDFs

---

## 🔗 Menu Navigation

```
Dashboard
├── Customers
├── Products
├── Items ⭐ NEW
├── Create Invoice
├── Invoices (History)
├── Reports
├── Settings
└── Logout
```

---

## 📞 Help & Support

### Issue: Item code not auto-filling
- Verify item code is correct (case doesn't matter: `cake-001` = `CAKE-001`)
- Check Items page - make sure item exists

### Issue: PDF not downloading
- Ensure reportlab is installed: `pip install reportlab==4.0.9`
- Try a different browser
- Check MongoDB connection

### Issue: Can't create invoice
- Select a customer first (required)
- Add at least one item
- Check that quantities are valid numbers

### Issue: MongoDB connection error
- Ensure MongoDB is running
- Check connection string in `config.py`
- Default: `mongodb://localhost:27017/`

---

## 🎓 Tips & Tricks

1. **Item Code Format**: Use descriptive codes like:
   - `CAKE-001`, `CAKE-002` (for cakes)
   - `BREAD-001`, `BREAD-002` (for breads)
   - `BEVERAGE-01` (for beverages)

2. **Quantity Units**: Include unit in quantity field:
   - ✅ "10 kg"
   - ✅ "5 meters"
   - ✅ "100 pieces"
   - ✅ "2 boxes"

3. **Bulk Operations**: You can:
   - Search for items by partial name
   - Filter invoices by date range
   - Export reports to CSV

4. **Keyboard Shortcuts**:
   - Tab key: Move to next field
   - Enter: Submit forms
   - Ctrl+P: Print current page (when viewing invoice)

---

## 📚 More Information

See `IMPLEMENTATION_SUMMARY.md` for detailed technical documentation.

---

**Version**: 1.0  
**Status**: ✅ Ready to Use  
**Last Updated**: 2026-06-04
