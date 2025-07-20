import sqlite3
import datetime
import os

# DB file path (reuse existing DB)
DB_FILE = "data/database.db"


def initialize_jobwork_db():
    """
    Creates the tables for job work invoices if not already present
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Job Work Invoices Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobwork_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            customer_id INTEGER,
            billing_type TEXT, -- Normal Bill or GST Bill
            subtotal REAL,
            tax_amount REAL,
            total_amount REAL,
            paid_amount REAL,
            balance REAL,
            payment_method TEXT,
            status TEXT,  -- ✅ Added missing column
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    # Job Work Items Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobwork_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            description TEXT,
            amount REAL,
            FOREIGN KEY (invoice_id) REFERENCES jobwork_invoices(id)
        )
    ''')

    conn.commit()
    conn.close()


def get_next_jobwork_invoice_number():
    """
    Returns the next Job Work Invoice Number
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    today = datetime.datetime.now().strftime("%Y%m%d")
    c.execute('''
        SELECT invoice_no FROM jobwork_invoices
        WHERE invoice_no LIKE ?
        ORDER BY invoice_no DESC LIMIT 1
    ''', (f"JW-{today}%",))
    last_invoice = c.fetchone()

    if last_invoice:
        last_number = int(last_invoice[0].split("-")[-1])
        next_number = last_number + 1
    else:
        next_number = 1

    conn.close()
    return f"JW-{today}-{next_number:03d}"


def save_jobwork_invoice(customer_id, billing_type, subtotal, tax_amount,
                         total_amount, paid_amount, balance,
                         payment_method, status, items):
    """
    Saves a job work invoice with its items to the database
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Generate unique invoice number
    invoice_no = "JW-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    # Insert into jobwork_invoices
    c.execute('''
        INSERT INTO jobwork_invoices
        (invoice_no, customer_id, billing_type, subtotal, tax_amount, total_amount,
         paid_amount, balance, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        invoice_no, customer_id, billing_type, subtotal, tax_amount, total_amount,
        paid_amount, balance, payment_method, status
    ))

    invoice_id = c.lastrowid

    # Insert job work items
    for item in items:
        c.execute('''
            INSERT INTO jobwork_items (invoice_id, description, amount)
            VALUES (?, ?, ?)
        ''', (invoice_id, item['description'], item['amount']))

    conn.commit()
    conn.close()
    return invoice_no


def get_all_jobwork_invoices():
    """
    Fetch all Job Work invoices with customer name.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''
        SELECT jw.invoice_no, c.name, jw.date, jw.total_amount,
               jw.paid_amount, jw.balance, jw.payment_method, jw.status
        FROM jobwork_invoices jw
        LEFT JOIN customers c ON jw.customer_id = c.id
        ORDER BY jw.date DESC
    ''')

    rows = c.fetchall()
    conn.close()
    return rows


def get_jobwork_invoice_items(invoice_no):
    """
    Fetch all job work items for a specific invoice.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get invoice_id
    c.execute('''
        SELECT id FROM jobwork_invoices WHERE invoice_no=?
    ''', (invoice_no,))
    row = c.fetchone()
    if not row:
        conn.close()
        return []

    invoice_id = row[0]

    # Get items
    c.execute('''
        SELECT description, amount FROM jobwork_items
        WHERE invoice_id=?
    ''', (invoice_id,))

    items = c.fetchall()
    conn.close()

    return [{"description": desc, "amount": amt} for desc, amt in items]
