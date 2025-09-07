# scripts/create_dummy_db.py
import os
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "data/database.db"


def _ensure_dir():
    d = os.path.dirname(DB_FILE)
    if d and not os.path.exists(d):
        os.makedirs(d)


def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def recreate_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed existing {DB_FILE}")
    _ensure_dir()
    conn = _connect()
    cur = conn.cursor()

    # Company profile (single-row table)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        company_name TEXT,
        trn_no TEXT,
        address_line1 TEXT,
        address_line2 TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        phone1 TEXT,
        phone2 TEXT,
        email TEXT,
        website TEXT,
        bank_name TEXT,
        account_name TEXT,
        account_number TEXT,
        iban TEXT,
        swift_code TEXT,
        logo_path TEXT
    )
    """)

    # Customers + outlets
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        trn_no TEXT,
        email TEXT,
        phone TEXT,
        remarks TEXT,
        disabled INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_outlet (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        outlet_code TEXT NOT NULL,
        outlet_name TEXT,
        address_line1 TEXT,
        address_line2 TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        phone TEXT,
        remarks TEXT,
        disabled INTEGER DEFAULT 0,
        FOREIGN KEY(customer_id) REFERENCES customer(id),
        UNIQUE(customer_id, outlet_code)
    )
    """)

    # Salesman
    cur.execute("""
    CREATE TABLE IF NOT EXISTS salesman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        remarks TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Item master + stock
    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        uom TEXT NOT NULL,
        per_box_qty INTEGER DEFAULT 1,
        vat_percentage REAL DEFAULT 0,
        selling_price REAL DEFAULT 0,
        hsn_code TEXT DEFAULT '',
        remarks TEXT DEFAULT '',
        low_stock_level INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        batch_no INTEGER NOT NULL,
        purchase_price REAL NOT NULL,
        expiry_date TEXT,
        stock_type TEXT NOT NULL CHECK(stock_type IN ('purchase','return','damaged','adjustment')),
        quantity REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(item_id) REFERENCES item_master(id),
        UNIQUE(item_id, batch_no)
    )
    """)

    # Invoice + invoice items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE NOT NULL,
        invoice_date TEXT NOT NULL,
        customer_id INTEGER,
        bill_to TEXT,
        ship_to TEXT,
        lpo_no TEXT,
        discount REAL DEFAULT 0,
        total_amount REAL NOT NULL,
        vat_amount REAL NOT NULL,
        net_total REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        balance REAL DEFAULT 0,
        paid_amount REAL DEFAULT 0,
        remarks TEXT,
        status TEXT DEFAULT 'Active',
        salesman_id INTEGER,
        FOREIGN KEY(customer_id) REFERENCES customer(id),
        FOREIGN KEY(salesman_id) REFERENCES salesman(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoice_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        serial_no INTEGER NOT NULL,
        item_code TEXT,
        item_name TEXT,
        uom TEXT,
        per_box_qty INTEGER,
        quantity REAL NOT NULL,
        rate REAL NOT NULL,
        sub_total REAL NOT NULL,
        vat_percentage REAL NOT NULL,
        vat_amount REAL NOT NULL,
        net_amount REAL NOT NULL,
        FOREIGN KEY(invoice_id) REFERENCES invoice(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()
    print("Created schema.")


def seed_data():
    conn = _connect()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    # company_profile single row (id = 1)
    cur.execute("SELECT COUNT(*) FROM company_profile")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO company_profile (id, company_name, trn_no, address_line1, address_line2, city, state, country,
                                     phone1, phone2, email, website, bank_name, account_name, account_number, iban, swift_code, logo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1,
              "BillMate Solutions LLC",
              "TRN987654321",
              "Suite 100, Business Bay",
              "P.O. Box 12345",
              "Dubai",
              "Dubai",
              "UAE",
              "+971501234567",
              "+971502345678",
              "info@billmate.example",
              "www.billmate.example",
              "Emirates Bank",
              "BillMate Solutions LLC",
              "000123456789",
              "AE070000000000000000000",
              "EBILAEAD",
              "data/logos/billmate_logo.png"))
        print("Inserted default company profile.")

    # sample customers
    custs = [
        ("CUST-0001", "Al Noor Trading", "TRN111222333",
         "sales@alnoor.example", "+971501110000", "Regular customer"),
        ("CUST-0002", "Gulf Supplies", "TRN222333444",
         "sales@gulfsup.example", "+971509990000", "Priority"),
        ("CUST-0003", "One-time Buyer", None,
         "contact@onet.example", "+971500000001", "Occasional")
    ]
    for code, name, trn, email, phone, remarks in custs:
        cur.execute("SELECT id FROM customer WHERE customer_code = ?", (code,))
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO customer (customer_code, name, trn_no, email, phone, remarks, disabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (code, name, trn, email, phone, remarks, now, now))
    print("Inserted customers.")

    # outlets for CUST-0001 and CUST-0002
    # find customer ids
    cur.execute("SELECT id FROM customer WHERE customer_code = 'CUST-0001'")
    c1 = cur.fetchone()[0]
    cur.execute("SELECT id FROM customer WHERE customer_code = 'CUST-0002'")
    c2 = cur.fetchone()[0]

    outlets = [
        (c1, "OUT-001", "Al Noor - Deira", "Deira St 22", "",
         "Deira", "Dubai", "UAE", "+971501110001", "Main outlet"),
        (c1, "OUT-002", "Al Noor - Jabel Ali", "JAFza St 3", "",
         "Jabel Ali", "Dubai", "UAE", "+971501110002", "Warehouse"),
        (c2, "OUT-001", "Gulf Supplies - HQ", "Port Rd 5", "",
         "Port Area", "Sharjah", "UAE", "+971509990001", "HQ")
    ]
    for oc in outlets:
        cur.execute(
            "SELECT id FROM customer_outlet WHERE customer_id = ? AND outlet_code = ?", (oc[0], oc[1]))
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO customer_outlet (customer_id, outlet_code, outlet_name, address_line1, address_line2, city, state, country, phone, remarks, disabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, oc)
    print("Inserted outlets.")

    # salesmen
    salesmen = [
        ("EMP-001", "Mohammed Ali", "+971500010001",
         "mohammed@billmate.example", "Top performer"),
        ("EMP-002", "Sara Khan", "+971500010002",
         "sara@billmate.example", "Field sales")
    ]
    for emp_id, name, phone, email, remarks in salesmen:
        cur.execute("SELECT id FROM salesman WHERE emp_id = ?", (emp_id,))
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO salesman (emp_id, name, phone, email, remarks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (emp_id, name, phone, email, remarks, now, now))
    print("Inserted salesmen.")

    # items (master)
    items = [
        ("ITEM001", "Mineral Water 1L", "pcs", 12,
         5.0, 2.0, "2201", "Bottled water", 20),
        ("ITEM002", "Cooking Oil 1L", "ltr", 6,
         5.0, 12.0, "1507", "Edible oil", 10),
        ("ITEM003", "Face Mask Box", "pcs", 50,
         5.0, 25.0, "6307", "Box of masks", 5),
        ("ITEM004", "Detergent 2kg", "kg", 1,
         5.0, 18.0, "3402", "Detergent powder", 8)
    ]
    for code, name, uom, per_box, vat, sell_price, hsn, remarks, low_level in items:
        cur.execute("SELECT id FROM item_master WHERE item_code = ?", (code,))
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO item_master (item_code, name, uom, per_box_qty, vat_percentage, selling_price, hsn_code, remarks, low_stock_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, uom, per_box, vat, sell_price, hsn, remarks, low_level))
    print("Inserted item master records.")

    # stock batches (for each item create a few batches)
    # find item ids
    cur.execute("SELECT id, item_code FROM item_master")
    item_rows = cur.fetchall()
    item_map = {row[1]: row[0] for row in item_rows}

    # create sample batches with different purchase prices and expiry dates
    batches = [
        (item_map["ITEM001"], 1, 0.5, (datetime.now() +
         timedelta(days=365)).date().isoformat(), "purchase", 200),
        (item_map["ITEM001"], 2, 0.6, (datetime.now() +
         timedelta(days=450)).date().isoformat(), "purchase", 150),
        (item_map["ITEM002"], 1, 8.0, (datetime.now() +
         timedelta(days=400)).date().isoformat(), "purchase", 80),
        (item_map["ITEM003"], 1, 15.0, None, "purchase", 40),
        (item_map["ITEM004"], 1, 10.0, (datetime.now() +
         timedelta(days=200)).date().isoformat(), "purchase", 30),
    ]
    for item_id, batch_no, purchase_price, expiry, stype, qty in batches:
        # use batch_no from sequence; if conflict skip
        cur.execute(
            "SELECT id FROM stock WHERE item_id = ? AND batch_no = ?", (item_id, batch_no))
        if not cur.fetchone():
            tnow = datetime.now().isoformat(timespec="seconds")
            cur.execute("""
            INSERT INTO stock (item_id, batch_no, purchase_price, expiry_date, stock_type, quantity, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, batch_no, purchase_price, expiry, stype, qty, tnow, tnow))
    print("Inserted stock batches.")

    conn.commit()

    # helper - reduce stock FIFO (oldest created_at first)
    def reduce_stock_quantity(item_code: str, qty_to_reduce: float):
        if qty_to_reduce <= 0:
            return
        # use connection and cursor
        cursor = conn.cursor()
        # find item_id
        cursor.execute(
            "SELECT id FROM item_master WHERE item_code = ?", (item_code,))
        r = cursor.fetchone()
        if not r:
            raise ValueError("Item not found: " + item_code)
        item_id = r[0]
        # find batches with positive quantity (oldest first)
        cursor.execute("""
            SELECT id, quantity FROM stock
            WHERE item_id = ? AND quantity > 0
            ORDER BY created_at ASC, id ASC
        """, (item_id,))
        rows = cursor.fetchall()
        remaining = qty_to_reduce
        for stock_id, q in rows:
            if remaining <= 0:
                break
            deduct = min(q, remaining)
            new_q = q - deduct
            cursor.execute("UPDATE stock SET quantity = ?, updated_at = ? WHERE id = ?",
                           (new_q, datetime.now().isoformat(timespec="seconds"), stock_id))
            remaining -= deduct
        if remaining > 0:
            raise ValueError(
                f"Insufficient stock for {item_code}, short by {remaining}")

    # Create two invoices and invoice_items and reduce stock accordingly
    # Invoice 1: RAD-0001 (fully paid)
    def next_invoice_no(prefix="RAD"):
        cur = conn.cursor()
        cur.execute("SELECT invoice_no FROM invoice ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return f"{prefix}-0001"
        last = row[0]
        try:
            p, n = last.split("-")
            return f"{p}-{int(n)+1:04d}"
        except Exception:
            return f"{prefix}-0001"

    # create invoice 1
    cur = conn.cursor()
    inv1_no = next_invoice_no()
    inv1_date = datetime.now().isoformat(timespec="seconds")
    # customer_id c1
    cur.execute("SELECT id FROM customer WHERE customer_code = 'CUST-0001'")
    cust1_id = cur.fetchone()[0]
    # salesman id
    cur.execute("SELECT id FROM salesman WHERE emp_id = 'EMP-001'")
    sm1 = cur.fetchone()[0]
    items_inv1 = [
        {"item_code": "ITEM001", "item_name": "Mineral Water 1L", "uom": "pcs",
            "per_box_qty": 12, "quantity": 30, "rate": 2.0, "vat_percentage": 5.0, "free": False},
        {"item_code": "ITEM003", "item_name": "Face Mask Box", "uom": "pcs",
            "per_box_qty": 50, "quantity": 2, "rate": 25.0, "vat_percentage": 5.0, "free": False}
    ]
    total_amount = sum(it["quantity"] * it["rate"] for it in items_inv1)
    total_vat = sum((it["quantity"] * it["rate"]) *
                    it["vat_percentage"] / 100.0 for it in items_inv1)
    discount = 0.0
    taxable = total_amount - discount
    net_total = taxable + total_vat
    paid_amount = net_total
    balance = 0.0
    created = datetime.now().isoformat(timespec="seconds")
    cur.execute("""
    INSERT INTO invoice (invoice_no, invoice_date, customer_id, bill_to, ship_to, lpo_no, discount, total_amount, vat_amount, net_total, created_at, updated_at, balance, paid_amount, remarks, status, salesman_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (inv1_no, inv1_date, cust1_id, "Al Noor Trading\nDeira", "Al Noor - Deira\nDeira", "LPO-1001", discount, total_amount, total_vat, net_total, created, created, balance, paid_amount, "Sample Invoice 1", "Active", sm1))
    inv1_id = cur.lastrowid

    # invoice items & reduce stock
    for idx, it in enumerate(items_inv1, start=1):
        qty = it["quantity"]
        rate = it["rate"]
        sub = qty * rate
        vat_amt = sub * it["vat_percentage"] / 100.0
        net = sub + vat_amt
        cur.execute("""
        INSERT INTO invoice_item (invoice_id, serial_no, item_code, item_name, uom, per_box_qty, quantity, rate, sub_total, vat_percentage, vat_amount, net_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv1_id, idx, it["item_code"], it["item_name"], it["uom"], it["per_box_qty"], qty, rate, sub, it["vat_percentage"], vat_amt, net))
        # reduce stock
        reduce_stock_quantity(it["item_code"], qty)

    # Invoice 2: partial paid
    inv2_no = next_invoice_no()
    inv2_date = (datetime.now() - timedelta(days=2)
                 ).isoformat(timespec="seconds")
    cur.execute("SELECT id FROM customer WHERE customer_code = 'CUST-0002'")
    cust2_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM salesman WHERE emp_id = 'EMP-002'")
    sm2 = cur.fetchone()[0]
    items_inv2 = [
        {"item_code": "ITEM002", "item_name": "Cooking Oil 1L", "uom": "ltr",
            "per_box_qty": 6, "quantity": 5, "rate": 12.0, "vat_percentage": 5.0, "free": False},
        {"item_code": "ITEM004", "item_name": "Detergent 2kg", "uom": "kg", "per_box_qty": 1,
            "quantity": 3, "rate": 18.0, "vat_percentage": 5.0, "free": False}
    ]
    total_amount2 = sum(it["quantity"] * it["rate"] for it in items_inv2)
    total_vat2 = sum((it["quantity"] * it["rate"]) *
                     it["vat_percentage"] / 100.0 for it in items_inv2)
    discount2 = 0.0
    taxable2 = total_amount2 - discount2
    net_total2 = taxable2 + total_vat2
    paid2 = net_total2 * 0.5
    balance2 = net_total2 - paid2
    created2 = datetime.now().isoformat(timespec="seconds")
    cur.execute("""
    INSERT INTO invoice (invoice_no, invoice_date, customer_id, bill_to, ship_to, lpo_no, discount, total_amount, vat_amount, net_total, created_at, updated_at, balance, paid_amount, remarks, status, salesman_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (inv2_no, inv2_date, cust2_id, "Gulf Supplies\nHQ", "Gulf Supplies - HQ\nPort Area", "LPO-2002", discount2, total_amount2, total_vat2, net_total2, created2, created2, balance2, paid2, "Sample Invoice 2", "Active", sm2))
    inv2_id = cur.lastrowid

    for idx, it in enumerate(items_inv2, start=1):
        qty = it["quantity"]
        rate = it["rate"]
        sub = qty * rate
        vat_amt = sub * it["vat_percentage"] / 100.0
        net = sub + vat_amt
        cur.execute("""
        INSERT INTO invoice_item (invoice_id, serial_no, item_code, item_name, uom, per_box_qty, quantity, rate, sub_total, vat_percentage, vat_amount, net_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv2_id, idx, it["item_code"], it["item_name"], it["uom"], it["per_box_qty"], qty, rate, sub, it["vat_percentage"], vat_amt, net))
        reduce_stock_quantity(it["item_code"], qty)

    conn.commit()
    print("Inserted invoices and reduced stock accordingly.")

    # Print a short report
    print("\n=== DB Summary ===")
    cur.execute("SELECT COUNT(*) FROM customer")
    print("Customers:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM customer_outlet")
    print("Outlets:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM salesman")
    print("Salesmen:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM item_master")
    print("Items:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM stock")
    print("Stock batches:", cur.fetchone()[0])
    cur.execute("SELECT id, item_id, batch_no, quantity FROM stock")
    for r in cur.fetchall():
        print(" Stock row:", r)
    cur.execute("SELECT COUNT(*) FROM invoice")
    print("Invoices:", cur.fetchone()[0])
    cur.execute(
        "SELECT invoice_no, total_amount, net_total, paid_amount, balance FROM invoice")
    for r in cur.fetchall():
        print(" Invoice:", r)

    conn.close()


if __name__ == "__main__":
    recreate_db()
    seed_data()
    print("\nDone. Database created at:", os.path.abspath(DB_FILE))
