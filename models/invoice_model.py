import os
from models.stock_model import initialize_db, increase_stock_quantity

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
            name TEXT, phone TEXT, address TEXT, gst_no TEXT,
            outstanding_balance REAL DEFAULT 0.0
        )
    ''')
    # Invoices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE, customer_id INTEGER,
            date TEXT, total_amount REAL, paid_amount REAL, balance REAL,
            payment_method TEXT, status TEXT, remarks TEXT DEFAULT '', discount REAL DEFAULT 0.0,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    # Invoice Items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER, item_code TEXT,
            item_name TEXT, hsn_code TEXT, gst_percent REAL, price REAL, qty INTEGER, total REAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    ''')
    # Migrations for older tables
    c.execute("PRAGMA table_info(invoices)")
    columns = [col[1] for col in c.fetchall()]
    if "remarks" not in columns: c.execute("ALTER TABLE invoices ADD COLUMN remarks TEXT DEFAULT ''")
    if "discount" not in columns: c.execute("ALTER TABLE invoices ADD COLUMN discount REAL DEFAULT 0.0")
    conn.commit()
    conn.close()


def save_customer(name, phone, address, gst_no=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id FROM customers WHERE name=? AND phone=?', (name.strip(), phone.strip()))
    result = c.fetchone()
    if result:
        customer_id = result[0]
    else:
        c.execute('INSERT INTO customers (name, phone, address, gst_no) VALUES (?, ?, ?, ?)',
                  (name.strip(), phone.strip(), address, gst_no))
        customer_id = c.lastrowid
    conn.commit()
    conn.close()
    return customer_id

def update_customer_details(old_phone, name, new_phone, address):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE customers SET name=?, phone=?, address=? WHERE phone=?', (name, new_phone, address, old_phone))
    conn.commit()
    conn.close()


def get_next_invoice_number():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = datetime.datetime.now().strftime("%Y%m%d")
    prefix = f"INV-{today}-"
    c.execute("SELECT invoice_no FROM invoices WHERE invoice_no LIKE ? ORDER BY invoice_no DESC LIMIT 1", (f"{prefix}%",))
    row = c.fetchone()
    next_seq = int(row[0].split("-")[-1]) + 1 if row else 1
    conn.close()
    return f"{prefix}{next_seq:03d}"


def save_invoice(customer_id, total_amount, paid_amount, balance, payment_method, status, items, discount=0.0, invoice_no=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        if not invoice_no:
            invoice_no = "INV-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        c.execute('''
            INSERT INTO invoices (invoice_no, customer_id, date, total_amount, paid_amount, balance, payment_method, status, discount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (invoice_no, customer_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              total_amount, paid_amount, balance, payment_method, status, discount))
        invoice_id = c.lastrowid
        for item in items:
            c.execute('''
                INSERT INTO invoice_items (invoice_id, item_code, item_name, hsn_code, gst_percent, price, qty, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item['code'], item['name'], item['hsn'], item['gst'], item['price'], item['qty'], item['total']))
        if balance > 0:
            c.execute('UPDATE customers SET outstanding_balance = outstanding_balance + ? WHERE id=?', (balance, customer_id))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        conn.close()
    return invoice_no


def get_invoice_details_by_no(invoice_no):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT i.*, c.name as customer_name FROM invoices i LEFT JOIN customers c ON i.customer_id = c.id WHERE i.invoice_no = ?', (invoice_no,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_invoice_items_by_no(invoice_no):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id FROM invoices WHERE invoice_no = ?", (invoice_no,))
    invoice_row = c.fetchone()
    if not invoice_row: return []
    c.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_row['id'],))
    items = c.fetchall()
    conn.close()
    return [dict(item) for item in items]


def get_all_invoices():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT i.invoice_no, c.name, i.date, i.total_amount, i.discount, i.paid_amount, i.balance, i.payment_method, i.status, i.remarks FROM invoices i LEFT JOIN customers c ON i.customer_id = c.id ORDER BY i.date DESC')
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, name, phone, address, gst_no, (SELECT SUM(total_amount) FROM invoices WHERE customer_id = customers.id) as total_sales, outstanding_balance FROM customers ORDER BY name')
    rows = c.fetchall()
    conn.close()
    return rows

def get_customer_sales_summary(phone):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(total_amount), COUNT(*) FROM invoices WHERE customer_id = (SELECT id FROM customers WHERE phone=?) AND balance > 0', (phone,))
    row = c.fetchone()
    conn.close()
    return row

def update_full_invoice(invoice_no, header_data, items_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT id, customer_id, balance FROM invoices WHERE invoice_no = ?", (invoice_no,))
        res = c.fetchone()
        if not res: raise ValueError("Invoice not found")
        invoice_id, customer_id, original_balance = res
        new_balance = header_data.get('balance', 0.0)
        c.execute("UPDATE customers SET outstanding_balance = (outstanding_balance - ?) + ? WHERE id = ?", (original_balance, new_balance, customer_id))
        c.execute('UPDATE invoices SET total_amount=?, paid_amount=?, balance=?, status=?, remarks=?, discount=? WHERE invoice_no=?',
                  (header_data.get('total_amount', 0.0), header_data.get('paid_amount', 0.0), new_balance, header_data.get('status', 'Unpaid'),
                   header_data.get('remarks', ''), header_data.get('discount', 0.0), invoice_no))
        c.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        for item in items_data:
            c.execute('INSERT INTO invoice_items (invoice_id, item_code, item_name, hsn_code, gst_percent, price, qty, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                      (invoice_id, item.get('code') or item.get('item_code'), item.get('name') or item.get('item_name'), item.get('hsn') or item.get('hsn_code'),
                       item.get('gst') or item.get('gst_percent'), item.get('price'), item.get('qty'), item.get('total')))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        conn.close()

def cancel_invoice(invoice_no):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT id, customer_id, balance, status FROM invoices WHERE invoice_no = ?", (invoice_no,))
        res = c.fetchone()
        if not res: raise ValueError("Invoice not found")
        invoice_id, customer_id, original_balance, current_status = res
        if current_status == 'Cancelled': raise ValueError("Invoice is already cancelled.")
        c.execute("SELECT item_code, qty FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        items_to_return = c.fetchall()
        for item_code, qty in items_to_return:
            if item_code and qty > 0:
                increase_stock_quantity(item_code, qty)
        c.execute("UPDATE invoices SET status = 'Cancelled', balance = 0, paid_amount = total_amount WHERE invoice_no = ?", (invoice_no,))
        if customer_id and original_balance > 0:
            c.execute("UPDATE customers SET outstanding_balance = outstanding_balance - ? WHERE id = ?", (original_balance, customer_id))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        conn.close()

def update_invoice_entry(invoice_no, paid_amount, balance, status, remarks=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT customer_id, balance FROM invoices WHERE invoice_no = ?", (invoice_no,))
        res = c.fetchone()
        if not res:
            raise ValueError("Invoice not found")
        customer_id, original_balance = res

        c.execute("UPDATE customers SET outstanding_balance = (outstanding_balance - ?) + ? WHERE id = ?",
                  (original_balance, balance, customer_id))

        c.execute('''
            UPDATE invoices
            SET paid_amount=?, balance=?, status=?, remarks=?
            WHERE invoice_no=?
        ''', (paid_amount, balance, status, remarks, invoice_no))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

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