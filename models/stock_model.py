# models/stock_model.py
import datetime
import sqlite3
import os
import time
from typing import List, Tuple, Dict, Optional
from contextlib import closing

DB_FILE = "data/database.db"

if not os.path.exists("data"):
    os.makedirs("data")


# ------------------------
# Connection helper
# ------------------------
def _connect(timeout: float = 30.0) -> sqlite3.Connection:
    """
    Return a new sqlite3 connection configured for WAL and with foreign keys enabled.
    Each call returns a fresh connection (no sharing across threads).
    """
    conn = sqlite3.connect(DB_FILE, timeout=timeout,
                           isolation_level=None)  # we will control BEGIN/COMMIT explicitly
    # ensure pragmas
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        # some sqlite builds may not support WAL on some filesystems — ignore failure
        pass
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ------------------------
# DB init + migrations
# ------------------------
def init_db():
    """
    Initialize DB tables and ensure compatibility with older DBs by adding
    missing columns where needed. Safe to call multiple times.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create item_master
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        uom TEXT NOT NULL,             -- e.g. kg, liter, pcs, meter
        per_box_qty INTEGER DEFAULT 1,
        vat_percentage REAL DEFAULT 0,
        selling_price REAL DEFAULT 0,
        remarks TEXT DEFAULT '',
        low_stock_level INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Create stock table
    cursor.execute("""
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

    conn.commit()
    conn.close()


# ------------------------
# Item master helpers
# ------------------------
def add_item(item_code, name, uom="pcs", per_box_qty=1, vat_percentage=0.0,
             selling_price=0.0, remarks="", low_stock_level=0):
    """
    Insert a master item row into item_master. Returns the new row id.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    now = datetime.datetime.now().isoformat(timespec="seconds")

    cur.execute("""
    INSERT INTO item_master (
        item_code, name, uom, per_box_qty, vat_percentage,
        selling_price, remarks, low_stock_level, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (item_code, name, uom, int(per_box_qty),
          float(vat_percentage), float(selling_price),
          remarks, int(low_stock_level), now, now))

    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def update_item(item_code: str, **kwargs):
    """
    Update fields on item_master. Allowed keys:
      name, uom, per_box_qty, vat_percentage, selling_price, remarks, low_stock_level
    Example: update_item("ITEM001", selling_price=12.5, low_stock_level=20)
    """
    allowed = {"name", "uom", "per_box_qty", "vat_percentage",
               "selling_price", "remarks", "low_stock_level"}
    updates = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            values.append(v)
    if not updates:
        return
    values.append(item_code)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    sql = f"UPDATE item_master SET {', '.join(updates)} WHERE item_code = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def get_item_by_item_code(item_code: str) -> Optional[Tuple]:
    """
    Return the raw item_master row for given item_code, or None.
    Columns follow the table definition.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM item_master WHERE item_code = ?", (item_code,))
    row = cursor.fetchone()
    conn.close()
    return row


def set_low_stock_level(item_code: str, level: int):
    update_item(item_code, low_stock_level=int(level))


def get_low_stock_level(item_code: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT low_stock_level FROM item_master WHERE item_code = ?", (item_code,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 0
    return int(row[0] or 0)


# ------------------------
# Stock helpers
# ------------------------
def get_next_batch_no(item_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(batch_no) FROM stock WHERE item_id = ?", (item_id,))
    max_batch = cursor.fetchone()[0]
    conn.close()
    return (max_batch or 0) + 1


def add_stock(item_code: str,
              purchase_price: float,
              quantity: float,
              expiry_date: Optional[str] = None,
              stock_type: str = "purchase") -> int:
    """
    Add a new stock batch for an item_code. Returns batch_no.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM item_master WHERE item_code = ?", (item_code,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Item code {item_code} not found in item_master")
    item_id = row[0]

    batch_no = get_next_batch_no(item_id)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cursor.execute("""
    INSERT INTO stock (item_id, batch_no, purchase_price, expiry_date, stock_type, quantity, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (item_id, batch_no, float(purchase_price), expiry_date, stock_type, float(quantity), now, now))
    conn.commit()
    conn.close()
    return batch_no


def add_stock_batch(item_id: int, purchase_price: float, selling_price: float, quantity: float, expiry_date: Optional[str] = None, stock_type: str = "purchase") -> int:
    """
    Convenience wrapper for UI code that sometimes has item_id already.
    This will use item_id to create a batch; returns batch_no.
    Note: selling_price is stored in item_master (if provided) as well.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_code FROM item_master WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Item id not found")
    item_code = row[0]
    # Update selling price in master if provided
    if selling_price is not None:
        cursor.execute("UPDATE item_master SET selling_price = ? WHERE id = ?", (float(
            selling_price), item_id))
    conn.commit()
    conn.close()
    # create the batch (uses add_stock which opens its own connection)
    batch_no = add_stock(item_code, purchase_price=purchase_price,
                         quantity=quantity, expiry_date=expiry_date, stock_type=stock_type)
    return batch_no


def get_all_batches(item_code: str) -> List[Tuple]:
    """
    Return all batches for given item_code in ascending created_at order.
    Each tuple: (id, batch_no, purchase_price, quantity, expiry_date, stock_type, created_at, updated_at)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.id, s.batch_no, s.purchase_price, s.quantity, s.expiry_date, s.stock_type, s.created_at, s.updated_at
    FROM stock s
    JOIN item_master im ON im.id = s.item_id
    WHERE im.item_code = ?
    ORDER BY s.created_at ASC
    """, (item_code,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# ------------------------
# Internal reduction helpers
# ------------------------
def _reduce_using_cursor(cursor: sqlite3.Cursor, item_code: str, qty_to_reduce: float):
    """
    Helper that accepts a DB cursor and performs the FIFO reduction using that cursor.
    Expects quantity arithmetic and updates using the same DB connection.
    Raises ValueError if insufficient stock.
    """
    cursor.execute("""
        SELECT s.id, s.quantity
        FROM stock s
        JOIN item_master im ON im.id = s.item_id
        WHERE im.item_code = ? AND s.quantity > 0
        ORDER BY s.created_at ASC, s.id ASC
    """, (item_code,))
    batches = cursor.fetchall()

    remaining = float(qty_to_reduce)
    if not batches:
        raise ValueError(
            f"Not enough stock to reduce {qty_to_reduce} for item {item_code}")

    for stock_id, qty in batches:
        if remaining <= 0:
            break
        available = float(qty or 0)
        deduct = min(available, remaining)
        new_qty = round(available - deduct, 6)
        now = datetime.datetime.now().isoformat(timespec="seconds")
        cursor.execute(
            "UPDATE stock SET quantity = ?, updated_at = ? WHERE id = ?", (new_qty, now, stock_id))
        remaining -= deduct

    if remaining > 0:
        raise ValueError(
            f"Not enough stock to reduce {qty_to_reduce}, short by {remaining}")


def reduce_stock_quantity(item_code: str, qty_to_reduce: float, conn: Optional[sqlite3.Connection] = None):
    """
    Reduce stock using FIFO (oldest batch first).
    If `conn` is provided, use it (so callers can run this inside their transaction).
    Returns: dict { 'remaining_qty': float, 'low_stock_level': int, 'fell_below': bool }
    Raises ValueError if not enough stock.
    """
    qty_to_reduce = float(qty_to_reduce or 0)
    if qty_to_reduce <= 0:
        # nothing to do — return current totals
        with sqlite3.connect(DB_FILE) as tmpc:
            cur = tmpc.cursor()
            cur.execute("""
                SELECT IFNULL(SUM(s.quantity),0)
                FROM stock s
                JOIN item_master im ON im.id = s.item_id
                WHERE im.item_code = ?
            """, (item_code,))
            rem = float(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT IFNULL(low_stock_level,0) FROM item_master WHERE item_code = ?", (item_code,))
            low_row = cur.fetchone()
            low = int(low_row[0] or 0) if low_row else 0

            fell = (low > 0 and rem < low)
            return {'remaining_qty': rem, 'low_stock_level': low, 'fell_below': fell}

    def _post_stats(cursor_local):
        # compute remaining and low level after commit
        cursor_local.execute("""
            SELECT IFNULL(SUM(s.quantity),0)
            FROM stock s
            JOIN item_master im ON im.id = s.item_id
            WHERE im.item_code = ?
        """, (item_code,))
        remaining = float(cursor_local.fetchone()[0] or 0)
        cursor_local.execute(
            "SELECT IFNULL(low_stock_level,0) FROM item_master WHERE item_code = ?", (item_code,))
        low_row = cursor_local.fetchone()
        low = int(low_row[0] or 0) if low_row else 0
        fell = (low > 0 and remaining < low)
        return {'remaining_qty': remaining, 'low_stock_level': low, 'fell_below': fell}

    # If caller passed in an active connection, use it (no commit/close here).
    if conn is not None:
        cursor = conn.cursor()
        _reduce_using_cursor(cursor, item_code, qty_to_reduce)
        return _post_stats(cursor)

    # Otherwise, use our own short-lived connection/transaction
    with closing(_connect()) as local_conn:
        cur = local_conn.cursor()
        try:
            local_conn.execute("BEGIN")
            _reduce_using_cursor(cur, item_code, qty_to_reduce)
            local_conn.commit()
            return _post_stats(cur)
        except Exception:
            try:
                local_conn.rollback()
            except Exception:
                pass
            raise

# ------------------------
# Consolidation / queries
# ------------------------


def get_consolidated_stock() -> List[Tuple]:
    """
    Returns list of tuples:
    (item_code, name, total_qty, uom, selling_price, vat_percentage, low_stock_level, is_below)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT im.item_code,
           im.name,
           IFNULL(SUM(s.quantity), 0) as total_qty,
           im.uom,
           im.selling_price,
           IFNULL(im.vat_percentage, 5.0) as vat_percentage,
           IFNULL(im.low_stock_level, 0) as low_stock_level
    FROM item_master im
    LEFT JOIN stock s ON im.id = s.item_id
    GROUP BY im.id
    ORDER BY im.name COLLATE NOCASE
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for item_code, name, total_qty, uom, selling_price, vat_percentage, low_level in rows:
        total_qty = float(total_qty or 0)
        low_level = int(low_level or 0)
        # ensure vat is a float and sensible default
        try:
            vat_percentage = float(
                vat_percentage if vat_percentage is not None else 5.0)
        except Exception:
            vat_percentage = 5.0
        is_below = (low_level > 0 and total_qty < low_level)
        result.append((
            item_code, name, total_qty, uom,
            selling_price, vat_percentage, low_level, bool(is_below)
        ))
    return result


def get_items_below_own_threshold() -> List[Tuple]:
    """
    Return consolidated items where total_qty < low_stock_level and low_stock_level > 0.
    Same tuple format as get_consolidated_stock().
    """
    consolidated = get_consolidated_stock()
    return [r for r in consolidated if (r[5] > 0 and (r[2] or 0) < r[5])]


def get_low_stock_items(threshold: Optional[float] = None) -> List[Tuple]:
    """
    Backwards-compatible helper:
     - If threshold provided -> returns items with total_qty < threshold (global threshold).
     - If threshold is None -> returns items below their own low_stock_level.
    """
    if threshold is None:
        return get_items_below_own_threshold()
    consolidated = get_consolidated_stock()
    return [r for r in consolidated if (r[2] or 0) < float(threshold)]


# ------------------------
# Convenience helpers for UI compatibility
# ------------------------
def get_latest_item_details_by_code(item_code: str) -> Optional[Tuple]:
    """
    Return a tuple useful for UI selection boxes. Format:
    (item_id, name, item_code, uom,  vat_percentage, selling_price, total_qty)
    Returns None if item not found.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT im.id, im.name, im.item_code, im.uom,  im.vat_percentage, im.selling_price,
           IFNULL((SELECT SUM(s.quantity) FROM stock s WHERE s.item_id = im.id), 0)
    FROM item_master im
    WHERE im.item_code = ?
    """, (item_code,))
    row = cursor.fetchone()
    conn.close()
    return row


def add_stock_item(name: str, item_code: str, uom: str,  vat_percentage: float = 0.0, selling_price: float = 0.0) -> int:
    """
    UI-friendly wrapper that creates an item_master entry if missing and returns its id.
    """
    item_id = add_item(item_code=item_code, name=name, uom=uom, per_box_qty=1,
                       vat_percentage=vat_percentage, selling_price=selling_price, )
    return item_id
