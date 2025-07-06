import sqlite3
import os

DB_FILE = "data/database.db"

if not os.path.exists("data"):
    os.makedirs("data")

# Initialize database


def initialize_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Stock items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT  NOT NULL,
            unit TEXT NOT NULL,
            hsn_code TEXT NOT NULL,
            gst_percent REAL NOT NULL
        )
    ''')
    # Stock batches table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            available_qty INTEGER NOT NULL,
            purchase_date TEXT DEFAULT CURRENT_DATE,
            FOREIGN KEY (stock_id) REFERENCES stock(id)
        )
    ''')
    conn.commit()
    conn.close()


# Add stock item
def add_stock_item(name, code, unit, hsn_code, gst_percent):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO stock (name, code, unit, hsn_code, gst_percent) VALUES (?, ?, ?, ?, ?)",
              (name, code, unit, hsn_code, gst_percent))
    conn.commit()
    conn.close()

# Add stock batch


def add_stock_batch(stock_id, purchase_price, selling_price, quantity):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO stock_batches 
        (stock_id, purchase_price, selling_price, quantity, available_qty) 
        VALUES (?, ?, ?, ?, ?)
    ''', (stock_id, purchase_price, selling_price, quantity, quantity))
    conn.commit()
    conn.close()

# Get all stock items with batches


def get_stock_with_batches():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.name, s.code, s.unit, s.hsn_code, s.gst_percent,
               b.purchase_price, b.selling_price, b.quantity, b.available_qty, b.purchase_date
        FROM stock s
        LEFT JOIN stock_batches b ON s.id = b.stock_id
        ORDER BY s.name, b.purchase_date DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows
# Get stock item by ID


def get_item_by_code(code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM stock WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()
    return row


def get_consolidated_stock():
    """
    Get consolidated stock with total available quantity for each item code
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.name, s.code, s.unit, s.hsn_code, s.gst_percent,
               MAX(b.selling_price) as latest_selling_price,
               SUM(b.available_qty) as total_available_qty
        FROM stock s
        LEFT JOIN stock_batches b ON s.id = b.stock_id
        GROUP BY s.code
        ORDER BY s.name
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def get_latest_item_details_by_code(code):
    """
    Fetch the latest stock details for a given item code
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, s.code, s.unit, s.hsn_code, s.gst_percent,
               b.selling_price
        FROM stock s
        LEFT JOIN stock_batches b ON s.id = b.stock_id
        WHERE s.code = ?
        ORDER BY b.purchase_date DESC
        LIMIT 1
    """, (code,))
    row = c.fetchone()
    conn.close()
    return row  # Returns (stock_id, name, code, unit, hsn, gst, selling_price)


def get_all_batches():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT s.code, s.name, s.unit, s.hsn_code, s.gst_percent,
               b.purchase_price, b.selling_price, b.available_qty, b.purchase_date
        FROM stock s
        JOIN stock_batches b ON s.id = b.stock_id
        ORDER BY s.name, b.purchase_date DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def update_item_master(code, name, unit, hsn_code, gst_percent):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE stock
        SET name=?, unit=?, hsn_code=?, gst_percent=?
        WHERE code=?
    ''', (name, unit, hsn_code, gst_percent, code))
    conn.commit()
    conn.close()


def update_batch_details(code, purchase_price, selling_price, available_qty):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE stock_batches
        SET purchase_price=?, selling_price=?, available_qty=?
        WHERE stock_id = (
            SELECT id FROM stock WHERE code=?
        )
    ''', (purchase_price, selling_price, available_qty, code))
    conn.commit()
    conn.close()


def reduce_stock_quantity(item_code, qty_to_reduce):
    """
    Deduct quantity from the earliest available batches (FIFO).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get all batches of the item ordered by batch_id (FIFO)
    c.execute('''
        SELECT id, available_qty FROM stock_batches
        WHERE stock_id = (SELECT id FROM stock WHERE code=?)
        ORDER BY id
    ''', (item_code,))
    batches = c.fetchall()

    qty_left = qty_to_reduce

    for batch_id, available_qty in batches:
        if qty_left <= 0:
            break
        if available_qty >= qty_left:
            # Reduce from this batch
            c.execute('''
                UPDATE stock_batches
                SET available_qty = available_qty - ?
                WHERE id=?
            ''', (qty_left, batch_id))
            qty_left = 0
        else:
            # Set this batch qty to 0 and move to next batch
            c.execute('''
                UPDATE stock_batches
                SET available_qty = 0
                WHERE id=?
            ''', (batch_id,))
            qty_left -= available_qty

    conn.commit()
    conn.close()
