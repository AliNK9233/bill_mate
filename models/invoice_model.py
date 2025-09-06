# models/invoice_model.py
from models.stock_model import reduce_stock_quantity  # assume exists
import sqlite3
import os
from datetime import datetime
from contextlib import closing

DB_FILE = "data/database.db"
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


def _connect():
    """
    Centralize sqlite connection settings: increase timeout and
    enable WAL mode which reduces database locked errors in multi-operation flows.
    """
    conn = sqlite3.connect(
        # autocommit disabled via explicit transactions
        DB_FILE, timeout=30, isolation_level=None)
    # Set pragmas each connection
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_invoice_db():
    with closing(_connect()) as conn:
        cur = conn.cursor()
        # create tables if not exists
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
            remarks TEXT
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


# Helper to compute next invoice number
def get_next_invoice_no():
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute("SELECT invoice_no FROM invoice ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.commit()
    if not row:
        return "RAD-0001"
    prefix, num = row[0].split("-")
    next_num = int(num) + 1
    return f"{prefix}-{next_num:04d}"


def _get_next_invoice_no_in_txn(cur):
    """
    Generate next invoice number using the given DB cursor (inside the same transaction).
    Format: RAD-0001
    """
    cur.execute("SELECT invoice_no FROM invoice ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return "RAD-0001"
    try:
        prefix, num = row[0].split("-")
        return f"{prefix}-{int(num) + 1:04d}"
    except Exception:
        # fallback if unexpected format
        cur.execute("SELECT COUNT(*) FROM invoice")
        cnt = cur.fetchone()[0] or 0
        return f"RAD-{cnt+1:04d}"

# Import reduce_stock_quantity from stock model here to avoid circular imports at module import time


def create_invoice(bill_to, ship_to, items, lpo_no="", discount=0, customer_id=None, salesman_id=None, max_retries=5):
    """
    Create invoice atomically and reduce stock using the same DB connection.
    items: list of dicts with keys:
      item_code, item_name, uom, per_box_qty, quantity, rate, vat_percentage, free (bool)
    Returns invoice_no
    Retries on transient 'database is locked' errors.
    """
    attempt = 0
    last_exc = None

    while attempt < max_retries:
        attempt += 1
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")  # explicit transaction

            # generate invoice_no inside txn to reduce race window
            invoice_no = _get_next_invoice_no_in_txn(cur)
            now = datetime.now().isoformat(timespec="seconds")

            # compute totals safely (cast)
            total_amount = 0.0
            total_vat = 0.0
            parsed_items = []
            for it in items:
                qty = float(it.get("quantity", 0))
                free = bool(it.get("free", False))
                rate = 0.0 if free else float(it.get("rate", 0.0))
                sub = qty * rate
                vat_amt = sub * (float(it.get("vat_percentage", 0.0)) / 100.0)
                total_amount += sub
                total_vat += vat_amt
                parsed_items.append((it, qty, rate, vat_amt, sub, free))

            taxable = max(0.0, total_amount - float(discount or 0.0))
            net_total = taxable + total_vat

            # Insert invoice header
            cur.execute("""
            INSERT INTO invoice (
                invoice_no, invoice_date, customer_id, bill_to, ship_to, lpo_no,
                discount, total_amount, vat_amount, net_total, created_at, updated_at,
                balance, paid_amount, salesman_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_no, now, customer_id, bill_to, ship_to, lpo_no,
                  float(discount or 0.0), total_amount, total_vat, net_total, now, now, net_total, 0.0, salesman_id))

            invoice_id = cur.lastrowid

            # Insert items and reduce stock using the same connection
            for idx, (it, qty, rate, vat_amt, sub, free) in enumerate(parsed_items, start=1):
                vat_pct = float(it.get("vat_percentage", 0.0))
                net_amount = sub + vat_amt

                cur.execute("""
                INSERT INTO invoice_item (
                    invoice_id, serial_no, item_code, item_name, uom, per_box_qty,
                    quantity, rate, sub_total, vat_percentage, vat_amount, net_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (invoice_id, idx, it.get("item_code"), it.get("item_name"),
                      it.get("uom"), it.get("per_box_qty", 1),
                      qty, rate, sub, vat_pct, vat_amt, net_amount))

                # reduce stock on same conn (prevents separate writer locks)
                if not free:
                    reduce_stock_quantity(it.get("item_code"), qty, conn=conn)

            # commit and return
            conn.commit()
            return invoice_no

        except sqlite3.OperationalError as oe:
            # typical transient lock error -> rollback, close, backoff and retry
            last_exc = oe
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()

            if "locked" in str(oe).lower():
                backoff = 0.1 * (2 ** (attempt - 1))
                time.sleep(backoff)
                continue  # retry
            else:
                raise
        except Exception as e:
            # rollback and re-raise other exceptions (including ValueError from reduce_stock_quantity)
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # if exhausted retries
    raise sqlite3.OperationalError(
        f"Failed to create invoice after {max_retries} attempts: {last_exc}")


def fetch_invoice(invoice_no):
    """
    Fetch header and items for a given invoice_no.
    Returns (header_row_tuple, [item_row_tuples...]) or (None, None) if not found.
    """
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoice WHERE invoice_no = ?",
                    (invoice_no,))
        header = cur.fetchone()
        if not header:
            return None, None
        # invoice_item columns are as inserted above
        cur.execute("""
        SELECT id, serial_no, item_code, item_name, uom, per_box_qty, quantity, rate,
               sub_total, vat_percentage, vat_amount, net_amount
        FROM invoice_item WHERE invoice_id = ?
        ORDER BY serial_no
        """, (header[0],))
        items = cur.fetchall()
    return header, items


def get_all_invoices():
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT invoice_no, invoice_date, bill_to, ship_to, total_amount, vat_amount, net_total
            FROM invoice ORDER BY id DESC
        """)
        rows = cur.fetchall()
    return rows


def update_invoice_entry(invoice_no, **kwargs):
    allowed_fields = {
        "customer_id", "bill_to", "ship_to", "salesman_id",
        "total_amount", "paid_amount", "balance",
        "payment_method", "status", "remarks", "discount"
    }
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed_fields:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        raise ValueError("No valid fields to update.")
    values.append(datetime.now().isoformat())
    values.append(invoice_no)
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE invoice SET {', '.join(fields)}, updated_at = ? WHERE invoice_no = ?", values)
        conn.commit()
    return True


def get_customer_sales_summary(customer_code):
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM customer WHERE customer_code = ?", (customer_code,))
        row = cur.fetchone()
        if not row:
            return None
        customer_id = row[0]
        cur.execute(
            "SELECT SUM(total_amount) FROM invoice WHERE customer_id = ?", (customer_id,))
        total_sales = cur.fetchone()[0] or 0.0
        cur.execute(
            "SELECT COUNT(*) FROM invoice WHERE customer_id = ? AND balance > 0", (customer_id,))
        pending_count = cur.fetchone()[0] or 0
    return total_sales, pending_count
