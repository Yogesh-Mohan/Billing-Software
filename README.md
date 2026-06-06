# RED STUDIO - Billing Management Web Application

RED STUDIO is a fast, responsive, and modern billing management web application designed for a single business owner/operator. It provides dynamic customer lookup, inventory item tracking, automatic invoice generation (with auto-calculations and inventory deduction), comprehensive analytics reports, and print-optimized PDF invoice generation.

---

## Technical Stack
- **Frontend**: HTML5, CSS3, Bootstrap 5, Javascript, FontAwesome, Chart.js
- **Backend**: Python (Flask)
- **Database**: MongoDB (via PyMongo)

---

## Directory Structure
```
red_studio/
├── app.py                  # Main Flask application server script
├── config.py               # Setup parameters (MongoDB URIs, Keys, low-stock threshold)
├── requirements.txt        # Backend dependencies
├── db_seed.py              # MongoDB indices creation and administrator account seeding
├── database_schema_doc.md  # MongoDB Schema documentation (equivalent to SQL schema file)
├── templates/              # MVC Views / HTML Layouts
│   ├── base.html           # Core layout structure with responsive navigation sidebar
│   ├── login.html          # Administrator login portal
│   ├── dashboard.html      # Stats, sales charts, and low stock list alerts
│   ├── customers.html      # Customer database CRUD actions
│   ├── products.html       # Inventory product catalog CRUD actions
│   ├── invoice_create.html # Dynamic billing invoice creation tool
│   ├── invoice_view.html   # High-fidelity invoice details with print support
│   ├── invoices.html       # Searchable history of generated invoices
│   ├── reports.html        # Sales aggregations & CSV exports
│   └── settings.html       # Global studio business options & logo upload panels
└── static/                 # CSS/JS and Upload assets
    ├── css/
    │   └── style.css       # Premium responsive design theme & custom print layout rules
    ├── js/
    │   ├── main.js         # Core layout behaviors and modal parameters
    │   └── invoice.js      # Dynamic billing arithmetic and stock constraints validation
    └── uploads/            # Location of uploaded business logos
```

---

## Admin Credentials
When you run the database seeding script, it creates a default administrator profile:
- **Username**: `admin`
- **Password**: `admin123`

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.8+** must be installed.
- **MongoDB** must be installed and running locally on standard port `27017` (or configured via environment variables).

### 2. Set Up Virtual Environment (Optional but recommended)
Open terminal/cmd inside the project workspace directory and run:
```bash
python -m venv venv
venv\Scripts\activate      # On Windows
# source venv/bin/activate # On macOS/Linux
```

### 3. Install Dependencies
Install all required libraries specified in requirements:
```bash
pip install -r requirements.txt
```

### 4. Seed the Database
Run the seeding script to create database structures, indices, default admin settings, and sample mock items:
```bash
python db_seed.py
```

### 5. Launch the Web Application
Start the Flask application server:
```bash
python app.py
```
Open your web browser and navigate to: `http://localhost:5000/`
Login with username: `admin` and password: `admin123`
