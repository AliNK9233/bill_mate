# models/delivery_model.py


import sqlite3
import os
from datetime import datetime

DB_FILE = "data/database.db"


def ensure_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")


def initialize_delivery_tables():
    """
    Idempotently create tables required for delivery challans.
    """
    ensure_data_dir()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Header table
    c.execute("""
    CREATE TABLE IF NOT EXISTS delivery_challan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challan_no TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL,         -- ISO datetime
        company_profile_id INTEGER,       -- reference to company_profile (optional)
        to_address TEXT,                  -- manual recipient address
        to_gst_no TEXT,
        transporter_name TEXT,
        vehicle_no TEXT,
        delivery_location TEXT,
        description TEXT,                 -- manual description / reason
        related_invoice_no TEXT,          -- optional invoice reference
        total_qty REAL DEFAULT 0,
        created_by TEXT                   -- user name / operator optional
    )
    """)

    # Line items (either linked to stock by code or manual)
    c.execute("""
    CREATE TABLE IF NOT EXISTS delivery_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challan_id INTEGER NOT NULL,
        item_code TEXT,      -- nullable: may be manual entry
        item_name TEXT NOT NULL,
        hsn_code TEXT,
        qty REAL DEFAULT 0,
        unit TEXT,
        FOREIGN KEY (challan_id) REFERENCES delivery_challan(id) ON DELETE CASCADE
    )
    """)

    # Suggestions for description/autocomplete (user can add later)
    c.execute("""
    CREATE TABLE IF NOT EXISTS dc_description_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT UNIQUE NOT NULL,
        usage_count INTEGER DEFAULT 1,
        last_used TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Helpful indexes
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_dc_challan_no ON delivery_challan(challan_no);")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_dc_created_at ON delivery_challan(created_at);")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_di_challan_id ON delivery_items(challan_id);")

    conn.commit()
    conn.close()

def fetch_company_profile():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT name, address FROM company_profile LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            return {"name": row[0], "address": row[1]}
        return None

def get_next_challan_no(conn=None):
    """
    Generate next challan number: DC-YYYYMMDD-XXX where XXX increments per day.
    If conn provided, uses that connection (transaction friendly).
    """
    opened = False
    if conn is None:
        conn = sqlite3.connect(DB_FILE)
        opened = True
    c = conn.cursor()
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"DC-{today}-"
    c.execute(
        "SELECT challan_no FROM delivery_challan WHERE challan_no LIKE ? ORDER BY challan_no DESC LIMIT 1", (f"{prefix}%",))
    row = c.fetchone()
    if row:
        last_no = row[0]
        try:
            last_seq = int(last_no.split("-")[-1])
        except Exception:
            last_seq = 0
        next_seq = last_seq + 1
    else:
        next_seq = 1
    challan_no = f"{prefix}{next_seq:03d}"
    if opened:
        conn.close()
    return challan_no


def create_challan(header: dict, items: list):
    """
    Create a delivery challan with header and items.
    header: dict keys (optional/expected):
        company_profile_id (int) or None,
        to_address (str),
        to_gst_no (str),
        transporter_name (str),
        vehicle_no (str),
        delivery_location (str),
        description (str),
        related_invoice_no (str),
        created_by (str)
    items: list of dicts with keys:
        item_code (str or None), item_name (str), hsn_code (str), qty (number), unit (str)
    Returns: (challan_id, challan_no)
    """
    if not items or len(items) == 0:
        raise ValueError("At least one item is required to create a challan.")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    challan_no = get_next_challan_no(conn)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # compute total_qty
    total_qty = sum(float(item.get("qty", 0) or 0) for item in items)

    c.execute("""
        INSERT INTO delivery_challan
        (challan_no, created_at, company_profile_id, to_address, to_gst_no,
         transporter_name, vehicle_no, delivery_location, description, related_invoice_no,
         total_qty, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        challan_no, created_at, header.get("company_profile_id"),
        header.get("to_address"), header.get("to_gst_no"),
        header.get("transporter_name"), header.get("vehicle_no"),
        header.get("delivery_location"), header.get("description"),
        header.get("related_invoice_no"), total_qty, header.get("created_by")
    ))

    challan_id = c.lastrowid

    # insert items
    for it in items:
        c.execute("""
            INSERT INTO delivery_items
            (challan_id, item_code, item_name, hsn_code, qty, unit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            challan_id,
            it.get("item_code"),
            it.get("item_name"),
            it.get("hsn_code"),
            float(it.get("qty") or 0),
            it.get("unit")
        ))

    conn.commit()
    conn.close()

    # record description suggestion usage
    desc = header.get("description")
    if desc:
        add_description_suggestion(desc)

    return challan_id, challan_no


def add_description_suggestion(text):
    """
    Upsert a suggestion (increase usage_count if exists).
    """
    if not text or not text.strip():
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT id, usage_count FROM dc_description_suggestions WHERE text = ?", (text,))
    row = c.fetchone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if row:
        sid, usage = row
        c.execute(
            "UPDATE dc_description_suggestions SET usage_count = ?, last_used = ? WHERE id = ?", (usage + 1, now, sid))
    else:
        c.execute(
            "INSERT INTO dc_description_suggestions (text, usage_count, last_used) VALUES (?, ?, ?)", (text, 1, now))
    conn.commit()
    conn.close()


def get_description_suggestions(prefix: str = "", limit: int = 10):
    """
    Return suggestion texts that start with prefix (case-insensitive).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if prefix:
        pattern = f"{prefix}%"
        c.execute("SELECT text FROM dc_description_suggestions WHERE text LIKE ? ORDER BY usage_count DESC, last_used DESC LIMIT ?", (pattern, limit))
    else:
        c.execute(
            "SELECT text FROM dc_description_suggestions ORDER BY usage_count DESC, last_used DESC LIMIT ?", (limit,))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def get_challan(challan_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM delivery_challan WHERE id = ?", (challan_id,))
    header = c.fetchone()
    if not header:
        conn.close()
        return None
    # column names
    cols = [d[0] for d in c.description]
    header = dict(zip(cols, header))

    c.execute("SELECT item_code, item_name, hsn_code, qty, unit FROM delivery_items WHERE challan_id = ?", (challan_id,))
    items = [dict(zip([d[0] for d in c.description], row))
             for row in c.fetchall()]
    conn.close()
    return {"header": header, "items": items}


def get_challan_by_no(challan_no):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM delivery_challan WHERE challan_no = ?", (challan_no,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return get_challan(row[0])


def update_challan(challan_id: int, header: dict, items: list):
    """
    Update an existing challan (header + its items).
    - challan_id: existing delivery_challan.id to update
    - header: same keys as create_challan's header
    - items: list of dicts with item_code, item_name, hsn_code, qty, unit

    This function:
      * replaces header fields,
      * deletes existing items for challan and inserts new ones,
      * recalculates and updates total_qty,
      * updates/creates description suggestion if description provided.
    """
    if not challan_id:
        raise ValueError("challan_id is required for update.")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Ensure challan exists
    c.execute("SELECT 1 FROM delivery_challan WHERE id = ?", (challan_id,))
    if not c.fetchone():
        conn.close()
        raise ValueError(f"Challan id {challan_id} not found.")

    # compute total_qty
    total_qty = sum(float(item.get("qty", 0) or 0) for item in items)

    # Update header fields (only the columns present)
    c.execute("""
        UPDATE delivery_challan
        SET company_profile_id = ?, to_address = ?, to_gst_no = ?,
            transporter_name = ?, vehicle_no = ?, delivery_location = ?,
            description = ?, related_invoice_no = ?, total_qty = ?, created_by = ?
        WHERE id = ?
    """, (
        header.get("company_profile_id"),
        header.get("to_address"),
        header.get("to_gst_no"),
        header.get("transporter_name"),
        header.get("vehicle_no"),
        header.get("delivery_location"),
        header.get("description"),
        header.get("related_invoice_no"),
        total_qty,
        header.get("created_by"),
        challan_id
    ))

    # Delete old items and re-insert new ones
    c.execute("DELETE FROM delivery_items WHERE challan_id = ?", (challan_id,))
    for it in items:
        c.execute("""
            INSERT INTO delivery_items (challan_id, item_code, item_name, hsn_code, qty, unit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            challan_id,
            it.get("item_code"),
            it.get("item_name"),
            it.get("hsn_code"),
            float(it.get("qty") or 0),
            it.get("unit")
        ))

    conn.commit()
    conn.close()

    # Update description suggestion usage
    desc = header.get("description")
    if desc:
        add_description_suggestion(desc)

    return True


def list_challans(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, challan_no, created_at, to_address, total_qty FROM delivery_challan ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows
