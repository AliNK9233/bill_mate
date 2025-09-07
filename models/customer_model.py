# models/customer_model.py
import sqlite3
import os
from datetime import datetime

DB_FILE = "data/database.db"

if not os.path.exists("data"):
    os.makedirs("data")


def init_customer_db():
    """
    Create customer and customer_outlet tables (includes disabled column).
    Safe to call multiple times.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        trn_no TEXT,
        address_line1 TEXT,
        address_line2 TEXT,
        email TEXT,
        phone TEXT,
        remarks TEXT,
        disabled INTEGER DEFAULT 0,         -- 0 = enabled, 1 = disabled
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
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
        disabled INTEGER DEFAULT 0,         -- 0 = enabled, 1 = disabled
        FOREIGN KEY(customer_id) REFERENCES customer(id),
        UNIQUE(customer_id, outlet_code)
    )
    """)

    conn.commit()
    conn.close()


# ---------------------------
# Helpers for schema introspection
# ---------------------------
def table_has_column(table_name, column_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [r[1] for r in cursor.fetchall()]
    conn.close()
    return column_name in cols


# ---------------------------
# CRUD + utility functions
# ---------------------------
def get_next_customer_code():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT customer_code FROM customer ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        return "CUST-0001"
    prefix, num = row[0].split("-")
    return f"{prefix}-{int(num)+1:04d}"


def add_customer(name, trn_no=None, address_line1=None, address_line2=None, email=None, phone=None,  remarks=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    code = get_next_customer_code()
    now = datetime.now().isoformat(timespec="seconds")
    cursor.execute("""
    INSERT INTO customer (
        customer_code, name, trn_no, address_line1, address_line2,
        email, phone, remarks, disabled, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (code, name, trn_no, address_line1, address_line2, email, phone, remarks, 0, now, now))
    conn.commit()
    conn.close()
    return code


def update_customer(customer_code, **kwargs):
    """
    Update allowed customer fields.
    Allowed keys: name, trn_no, email, phone, remarks, disabled
    """
    allowed = {"name", "trn_no", 'address_line1',
               'address_line2', "email", "phone", "remarks", "disabled"}
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    # append updated_at and where param
    values.append(datetime.now().isoformat(timespec="seconds"))
    values.append(customer_code)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    sql = f"UPDATE customer SET {', '.join(fields)}, updated_at = ? WHERE customer_code = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def get_customer_by_code(customer_code):
    """
    Returns tuple row or None (legacy). Use get_customer_dict for robust access.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM customer WHERE customer_code = ?", (customer_code,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_customer_dict(customer_code):
    """
    Return customer as a dict with keys equal to column names.
    If 'disabled' column is missing, returns disabled:0 by default.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(customer)")
    cols = [r[1] for r in cursor.fetchall()]

    cursor.execute(
        f"SELECT * FROM customer WHERE customer_code = ?", (customer_code,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {}

    data = dict(zip(cols, row))
    if "disabled" not in data:
        data["disabled"] = 0
    return data


def add_outlet(customer_code, outlet_code, outlet_name, address_line1="", address_line2="", city="", state="", country="", phone="", remarks=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM customer WHERE customer_code = ?", (customer_code,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Customer not found")
    customer_id = row[0]
    cursor.execute("""
    INSERT INTO customer_outlet (
        customer_id, outlet_code, outlet_name, address_line1, address_line2,
        city, state, country, phone, remarks, disabled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (customer_id, outlet_code, outlet_name, address_line1, address_line2, city, state, country, phone, remarks))
    conn.commit()
    conn.close()


def get_outlets(customer_code, include_disabled=False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # detect disabled presence in outlet table
    cursor.execute("PRAGMA table_info(customer_outlet)")
    cols = [r[1] for r in cursor.fetchall()]
    has_disabled = "disabled" in cols

    if include_disabled or not has_disabled:
        cursor.execute("""
        SELECT o.* FROM customer_outlet o
        JOIN customer c ON c.id = o.customer_id
        WHERE c.customer_code = ?
        """, (customer_code,))
    else:
        cursor.execute("""
        SELECT o.* FROM customer_outlet o
        JOIN customer c ON c.id = o.customer_id
        WHERE c.customer_code = ? AND o.disabled = 0
        """, (customer_code,))
    rows = cursor.fetchall()
    conn.close()

    # if disabled not in schema, add a pseudo-column of 0 at the end of every row when returning
    if not has_disabled and rows:
        # extend tuples to include disabled=0 at end for compatibility
        new_rows = []
        for r in rows:
            new_rows.append(tuple(list(r) + [0]))
        return new_rows

    return rows


def get_all_customers(include_disabled=False):
    """
    Get all customers with basic details.
    Returns rows including address_line1 and address_line2 if present.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # detect schema
    cursor.execute("PRAGMA table_info(customer)")
    cols = [r[1] for r in cursor.fetchall()]
    has_disabled = "disabled" in cols
    has_address1 = "address_line1" in cols
    has_address2 = "address_line2" in cols

    if has_disabled:
        if include_disabled:
            if has_address1 and has_address2:
                cursor.execute("""
                    SELECT customer_code, name, trn_no,
                           address_line1, address_line2,
                           phone, remarks, disabled
                    FROM customer
                    ORDER BY id DESC
                """)
            else:
                cursor.execute("""
                    SELECT customer_code, name, trn_no, phone, remarks, disabled
                    FROM customer
                    ORDER BY id DESC
                """)
        else:
            if has_address1 and has_address2:
                cursor.execute("""
                    SELECT customer_code, name, trn_no,
                           address_line1, address_line2,
                           phone, remarks, disabled
                    FROM customer
                    WHERE disabled = 0
                    ORDER BY id DESC
                """)
            else:
                cursor.execute("""
                    SELECT customer_code, name, trn_no, phone, remarks, disabled
                    FROM customer
                    WHERE disabled = 0
                    ORDER BY id DESC
                """)
        rows = cursor.fetchall()
    else:
        # no disabled column in schema, so fake it with 0
        if has_address1 and has_address2:
            cursor.execute("""
                SELECT customer_code, name, trn_no,
                       address_line1, address_line2,
                       phone, remarks
                FROM customer
                ORDER BY id DESC
            """)
        else:
            cursor.execute("""
                SELECT customer_code, name, trn_no, phone, remarks
                FROM customer
                ORDER BY id DESC
            """)
        rows = cursor.fetchall()
        # append disabled=0 for each row
        rows = [tuple(list(r) + [0]) for r in rows]

    conn.close()
    return rows


# ---------------------------
# Enable / Disable helpers
# ---------------------------
def disable_customer(customer_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE customer SET disabled = 1, updated_at = ? WHERE customer_code = ?",
                   (datetime.now().isoformat(timespec="seconds"), customer_code))
    conn.commit()
    conn.close()


def enable_customer(customer_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE customer SET disabled = 0, updated_at = ? WHERE customer_code = ?",
                   (datetime.now().isoformat(timespec="seconds"), customer_code))
    conn.commit()
    conn.close()


def disable_outlet(outlet_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE customer_outlet SET disabled = 1 WHERE id = ?", (outlet_id,))
    conn.commit()
    conn.close()


def enable_outlet(outlet_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE customer_outlet SET disabled = 0 WHERE id = ?", (outlet_id,))
    conn.commit()
    conn.close()
