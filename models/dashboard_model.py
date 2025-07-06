import sqlite3
from models.stock_model import DB_FILE


def get_total_sales():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(total_amount) FROM invoices')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


def get_total_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM customers')
    result = c.fetchone()[0]
    conn.close()
    return result or 0


def get_total_pending_balance():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(balance) FROM invoices WHERE balance > 0')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


def get_top_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT c.name, c.phone, SUM(i.total_amount) as total_sales
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        GROUP BY c.id
        ORDER BY total_sales DESC
        LIMIT 5
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def get_low_stock_items():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT s.name, s.code, SUM(b.available_qty) as total_qty
        FROM stock s
        JOIN stock_batches b ON s.id = b.stock_id
        GROUP BY s.id
        HAVING total_qty <= 10
        ORDER BY total_qty ASC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows
