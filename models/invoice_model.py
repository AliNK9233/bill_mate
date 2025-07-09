import os
from models.stock_model import initialize_db

# Check if DB exists, if not create it
if not os.path.exists("data/database.db"):
    initialize_db()

import sqlite3
import datetime
from models.stock_model import DB_FILE


def initialize_invoice_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Customers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            address TEXT,
            gst_no TEXT,  -- ✅ Added GST No field
            outstanding_balance REAL DEFAULT 0.0
        )
    ''')

    # Invoices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            customer_id INTEGER,
            date TEXT,
            total_amount REAL,
            paid_amount REAL,
            balance REAL,
            payment_method TEXT,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    # Invoice Items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            item_code TEXT,
            item_name TEXT,
            hsn_code TEXT,
            gst_percent REAL,
            price REAL,
            qty INTEGER,
            total REAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    ''')

    conn.commit()
    conn.close()


def save_customer(name, phone, address, gst_no=None):
    """
    Save customer if not exists, return customer ID.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Check if customer exists
    c.execute('SELECT id FROM customers WHERE name=? AND phone=?', (name, phone))
    result = c.fetchone()

    if result:
        customer_id = result[0]
    else:
        c.execute('''
            INSERT INTO customers (name, phone, address, gst_no)
            VALUES (?, ?, ?, ?)
        ''', (name, phone, address, gst_no))
        customer_id = c.lastrowid

    conn.commit()
    conn.close()
    return customer_id


def get_next_invoice_number():
    """
    Get the next invoice number in sequence.
    Format: INV-YYYYMMDD-XXX
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = datetime.datetime.now().strftime("%Y%m%d")

    # Find last invoice for today
    c.execute('''
        SELECT invoice_no FROM invoices
        WHERE invoice_no LIKE ?
        ORDER BY invoice_no DESC LIMIT 1
    ''', (f"INV-{today}%",))
    last_invoice = c.fetchone()

    if last_invoice:
        # Increment last number
        last_number = int(last_invoice[0].split("-")[-1])
        next_number = last_number + 1
    else:
        next_number = 1  # Start fresh for today

    conn.close()
    return f"INV-{today}-{next_number:03d}"


def save_invoice(customer_id, total_amount, paid_amount, balance, payment_method, status, items):
    """
    Save invoice and related items
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create unique invoice number
    invoice_no = "INV-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    # Insert into invoices
    c.execute('''
        INSERT INTO invoices (invoice_no, customer_id, date, total_amount, paid_amount, balance, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (invoice_no, customer_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          total_amount, paid_amount, balance, payment_method, status))

    invoice_id = c.lastrowid

    # Insert items
    for item in items:
        c.execute('''
            INSERT INTO invoice_items (invoice_id, item_code, item_name, hsn_code, gst_percent, price, qty, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            invoice_id, item['code'], item['name'], item['hsn'],
            item['gst'], item['price'], item['qty'], item['total']
        ))

    # Update customer balance if unpaid/partial
    if balance > 0:
        c.execute('UPDATE customers SET outstanding_balance = outstanding_balance + ? WHERE id=?',
                  (balance, customer_id))

    conn.commit()
    conn.close()
    return invoice_no


def get_all_invoices():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT i.invoice_no, c.name, i.date, i.total_amount,
               i.paid_amount, i.balance, i.payment_method, i.status, i.remarks
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        ORDER BY i.date DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def get_invoices_by_month(month):
    """
    Get invoices for a specific month.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT i.invoice_no, c.name, i.date, i.total_amount,
               i.paid_amount, i.balance, i.payment_method, i.status, i.remarks
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        WHERE strftime('%m', i.date) = ?
        ORDER BY i.date DESC
    ''', (f"{month:02d}",))
    rows = c.fetchall()
    conn.close()
    return rows


def get_invoices_by_date_range(start_date, end_date):
    """
    Get invoices within a specific date range.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT i.invoice_no, c.name, i.date, i.total_amount,
               i.paid_amount, i.balance, i.payment_method, i.status, i.remarks
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        WHERE date(i.date) BETWEEN ? AND ?
        ORDER BY i.date DESC
    ''', (start_date, end_date))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT name, phone, address, gst_no,
               (SELECT SUM(total_amount) FROM invoices WHERE customer_id = customers.id) as total_sales,
               outstanding_balance
        FROM customers
        ORDER BY name
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def get_customer_sales_summary(phone):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''
        SELECT SUM(total_amount), COUNT(*)
        FROM invoices
        WHERE customer_id = (
            SELECT id FROM customers WHERE phone=?
        ) AND balance > 0
    ''', (phone,))
    row = c.fetchone()
    conn.close()
    return row


def update_customer_details(old_phone, name, new_phone, address):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE customers
        SET name=?, phone=?, address=?
        WHERE phone=?
    ''', (name, new_phone, address, old_phone))
    conn.commit()
    conn.close()


def update_invoice_entry(invoice_no, paid_amount, balance, status, remarks=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Add remarks column if missing
    c.execute("PRAGMA table_info(invoices)")
    columns = [col[1] for col in c.fetchall()]
    if "remarks" not in columns:
        c.execute("ALTER TABLE invoices ADD COLUMN remarks TEXT DEFAULT ''")

    c.execute('''
        UPDATE invoices
        SET paid_amount=?, balance=?, status=?, remarks=?
        WHERE invoice_no=?
    ''', (paid_amount, balance, status, remarks, invoice_no))
    conn.commit()
    conn.close()


def add_remarks_column_if_not_exists():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA table_info(invoices)")
    columns = [col[1] for col in c.fetchall()]
    if "remarks" not in columns:
        c.execute("ALTER TABLE invoices ADD COLUMN remarks TEXT DEFAULT ''")
    conn.commit()
    conn.close()
