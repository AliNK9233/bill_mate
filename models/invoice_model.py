# models/invoice_model.py
import time
from models.stock_model import reduce_stock_quantity  # assume exists
import sqlite3
import os
from datetime import date, datetime, timedelta
from contextlib import closing
from typing import Optional, List, Dict, Tuple, Union
from models.stock_model import reduce_stock_quantity, add_stock, _connect as _stock_connect

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

# helper: resolve customer identifier (accepts None, numeric id, or customer_code string)


def _resolve_shipto_id(conn, shipto_identifier) -> Optional[int]:
    if not shipto_identifier:
        return None
    cur = conn.cursor()
    try:
        sid = int(shipto_identifier)
        cur.execute("SELECT id FROM customer_outlet WHERE id = ?", (sid,))
        if cur.fetchone():
            return sid
    except Exception:
        pass
    # try outlet_code
    cur.execute("SELECT id FROM customer_outlet WHERE outlet_code = ? LIMIT 1", (str(
        shipto_identifier),))
    r = cur.fetchone()
    return r[0] if r else None


def _resolve_customer_id(conn, identifier) -> Optional[int]:
    """
    Accepts:
      - None -> returns None
      - numeric id (int or numeric string) -> verifies exists and returns int
      - customer_code (string) -> returns numeric id if found
    """
    if not identifier:
        return None
    cur = conn.cursor()
    try:
        # numeric?
        iid = int(identifier)
        cur.execute("SELECT id FROM customer WHERE id = ?", (iid,))
        if cur.fetchone():
            return iid
    except Exception:
        pass
    # treat as customer_code
    cur.execute("SELECT id FROM customer WHERE customer_code = ?",
                (str(identifier),))
    row = cur.fetchone()
    return row[0] if row else None


def _resolve_salesman_id(conn, identifier) -> Optional[int]:
    if not identifier:
        return None
    cur = conn.cursor()
    try:
        iid = int(identifier)
        cur.execute("SELECT id FROM salesman WHERE id = ?", (iid,))
        if cur.fetchone():
            return iid
    except Exception:
        pass
    # assume salesman code/emp id -- fallback lookup by first column 'code' or similar
    cur.execute("SELECT id FROM salesman WHERE salesman_code = ? OR emp_id = ? LIMIT 1", (str(
        identifier), str(identifier)))
    row = cur.fetchone()
    return row[0] if row else None


def _build_bill_ship_display(conn, bill_to_identifier, ship_to_identifier, resolved_customer_id):
    """
    Return (bill_to_display, ship_to_display)
    bill_to_identifier may be: customer_code / id / free-text.
    ship_to_identifier may be: outlet code / outlet id / free-text.
    We attempt to look up names/addresses where possible, otherwise fall back to the passed string.
    """
    cur = conn.cursor()

    bill_display = ""
    # If we have a numeric customer id, fetch its name + address lines + TRN
    if resolved_customer_id:
        cur.execute(
            "SELECT name, address_line1, address_line2, trn_no FROM customer WHERE id = ?", (resolved_customer_id,))
        r = cur.fetchone()
        if r:
            name, a1, a2, trn = r
            parts = [p for p in (name, a1, a2) if p]
            bill_display = "\n".join(parts)
            if trn:
                bill_display += f"\nTRN: {trn}"
    else:
        # try if bill_to_identifier is a customer_code string
        if bill_to_identifier:
            cur.execute("SELECT name, address_line1, address_line2, trn_no FROM customer WHERE customer_code = ?", (str(
                bill_to_identifier),))
            r = cur.fetchone()
            if r:
                name, a1, a2, trn = r
                parts = [p for p in (name, a1, a2) if p]
                bill_display = "\n".join(parts)
                if trn:
                    bill_display += f"\nTRN: {trn}"
            else:
                bill_display = str(bill_to_identifier)

    # ship_to: try outlets first (if ship_to_identifier looks like outlet code or numeric id)
    ship_display = ""
    if ship_to_identifier:
        # try numeric id
        try:
            sid = int(ship_to_identifier)
            cur.execute(
                "SELECT outlet_name, address_line1, address_line2 FROM customer_outlet WHERE id = ?", (sid,))
            r = cur.fetchone()
            if r:
                ship_display = "\n".join([p for p in (r[0], r[1], r[2]) if p])
        except Exception:
            # try outlet_code
            cur.execute("SELECT outlet_name, address_line1, address_line2 FROM customer_outlet WHERE outlet_code = ? LIMIT 1", (str(
                ship_to_identifier),))
            r = cur.fetchone()
            if r:
                ship_display = "\n".join([p for p in (r[0], r[1], r[2]) if p])
            else:
                # fallback: maybe passed the full display already
                ship_display = str(ship_to_identifier)

    return bill_display or "", ship_display or ""


def init_invoice_db():
    """
    Ensure invoice related tables exist.
    Safe to call multiple times.
    """
    with closing(_connect()) as conn:
        cur = conn.cursor()
        # clean, valid CREATE TABLE for invoice (no inline Python comments and no trailing comma)
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
            outlet_id INTEGER
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


def get_next_invoice_no(prefix: str = "RAD") -> str:
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT invoice_no FROM invoice ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return f"{prefix}-0001"
        try:
            last = row[0]
            pfx, num = last.rsplit("-", 1)
            next_num = int(num) + 1
            return f"{pfx}-{next_num:04d}"
        except Exception:
            # fallback: append incremental number
            return f"{prefix}-{int(datetime.now().timestamp())}"


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


def _as_iso(dt: Union[str, datetime, date, None], end_of_day: bool = False) -> Optional[str]:
    """
    Normalize a date/datetime/string to ISO string used in DB comparisons.
    Accepts: None, 'YYYY-MM-DD' or full iso string or datetime/date.
    If end_of_day True, and input is a date-only, return end of that day.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        # try parse YYYY-MM-DD or full iso
        try:
            if len(dt) == 10:
                d = datetime.strptime(dt, "%Y-%m-%d")
            else:
                d = datetime.fromisoformat(dt)
        except Exception:
            # as a fallback assume it's iso already
            return dt
    elif isinstance(dt, date) and not isinstance(dt, datetime):
        d = datetime(dt.year, dt.month, dt.day)
    else:
        d = dt

    if end_of_day:
        return d.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    else:
        # start of day
        return d.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def fetch_invoice(invoice_no: str) -> Tuple[Optional[Tuple], List[Tuple]]:
    """
    Return (header_row, list_of_item_rows)

    header_row: raw invoice row as returned by `SELECT * FROM invoice WHERE invoice_no = ?`
                (so header[0] == invoice.id)
    item_rows: list of tuples from invoice_item table for that invoice_id.

    This function is defensive: if invoice not found -> (None, []).
    """
    with closing(_connect()) as conn:
        cur = conn.cursor()

        # Header: select invoice fields and the salesman name (if available)
        cur.execute("""
            SELECT
                i.*,
                s.name as salesman_name
            FROM invoice i
            LEFT JOIN salesman s ON i.salesman_id = s.id
            WHERE i.invoice_no = ?
            LIMIT 1
        """, (invoice_no,))
        header = cur.fetchone()
        if not header:
            return None, []

        # Fetch invoice_item rows for this invoice id (order by serial_no)
        # Need invoice id from header (header[0] is id)
        invoice_id = header[0]
        cur.execute("""
            SELECT
                id, invoice_id, serial_no, item_code, item_name, uom, per_box_qty,
                quantity, rate, sub_total, vat_percentage, vat_amount, net_amount
            FROM invoice_item
            WHERE invoice_id = ?
            ORDER BY serial_no ASC, id ASC
        """, (invoice_id,))
        items = cur.fetchall()

        return header, items


def get_all_invoices(start_date: Optional[Union[str, datetime, date]] = None,
                     end_date: Optional[Union[str, datetime, date]] = None,
                     customer_id: Optional[int] = None,
                     salesman_id: Optional[int] = None,
                     status: Optional[str] = None,
                     pending_only: bool = False,
                     order_by: str = "invoice_date DESC") -> List[Tuple]:
    """
    Returns rows of invoice data with an extra 'salesman_name' column (last column).
    Columns returned (in order):
      invoice_no, invoice_date, customer_id, bill_to, ship_to,
      total_amount, vat_amount, net_total, balance, paid_amount, status, salesman_name, (and optionally more if DB contains them)
    """
    where_clauses = []
    params = []

    s_iso = _as_iso(start_date) if start_date is not None else None
    e_iso = _as_iso(
        end_date, end_of_day=True) if end_date is not None else None

    if s_iso:
        where_clauses.append("i.invoice_date >= ?")
        params.append(s_iso)
    if e_iso:
        where_clauses.append("i.invoice_date <= ?")
        params.append(e_iso)
    if customer_id is not None:
        where_clauses.append("i.customer_id = ?")
        params.append(customer_id)
    if salesman_id is not None:
        where_clauses.append("i.salesman_id = ?")
        params.append(salesman_id)
    if status is not None:
        where_clauses.append("i.status = ?")
        params.append(status)
    if pending_only:
        where_clauses.append("i.balance > 0")

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    sql = f"""
        SELECT
            i.invoice_no,
            i.invoice_date,
            i.customer_id,
            i.bill_to,
            i.ship_to,
            i.total_amount,
            i.vat_amount,
            i.net_total,
            i.balance,
            i.paid_amount,
            i.status,
            COALESCE(s.name, '') AS salesman_name,
            i.created_at,
            i.updated_at,
            i.outlet_id
        FROM invoice i
        LEFT JOIN salesman s ON i.salesman_id = s.id
        {where_sql}
        ORDER BY {order_by}
    """

    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return rows


def update_invoice_entry(invoice_no: str, **kwargs) -> bool:
    """
    Update allowed invoice fields. Example: update_invoice_entry("RAD-0001", paid_amount=500, balance=100)
    Allowed fields: bill_to, ship_to, lpo_no, discount, paid_amount, balance, remarks, status, salesman_id
    """
    allowed = {"bill_to", "ship_to", "lpo_no", "discount",
               "paid_amount", "balance", "remarks", "status", "salesman_id"}
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        raise ValueError("No updatable fields provided.")
    values.append(datetime.now().isoformat())
    values.append(invoice_no)
    sql = f"UPDATE invoice SET {', '.join(fields)}, updated_at = ? WHERE invoice_no = ?"
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(values))
        conn.commit()
        return True


def get_customer_sales_summary(customer_id: int) -> Tuple[float, int]:
    """
    Return (total_sales, pending_invoices_count) for given customer_id.
    total_sales sums net_total on invoices not cancelled.
    """
    with closing(_connect()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(net_total),0) FROM invoice WHERE customer_id = ? AND (status IS NULL OR status != 'Cancelled')", (customer_id,))
        total_sales = cur.fetchone()[0] or 0.0
        cur.execute(
            "SELECT COUNT(*) FROM invoice WHERE customer_id = ? AND balance > 0 AND (status IS NULL OR status != 'Cancelled')", (customer_id,))
        pending = cur.fetchone()[0] or 0
        return float(total_sales), int(pending)


def cancel_invoice(invoice_no: str, allow_days: int = 3) -> bool:
    """
    Cancel an invoice and restore stock inside the same DB transaction.
    - Will only cancel within `allow_days` of invoice_date.
    - Marks invoice.status = 'Cancelled' and inserts 'adjustment' stock batches to restore quantities.
    - Returns True on success, raises ValueError or sqlite3.OperationalError on failure.
    """
    if not invoice_no:
        raise ValueError("invoice_no required")

    conn = _connect()
    try:
        cur = conn.cursor()

        # fetch invoice header
        cur.execute(
            "SELECT id, invoice_date, status FROM invoice WHERE invoice_no = ?", (invoice_no,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Invoice not found.")
        inv_id, invoice_date_str, status = row

        if status and str(status).lower() in ("cancelled", "canceled", "voided"):
            raise ValueError("Invoice already cancelled.")

        # parse invoice_date defensively
        inv_dt = None
        try:
            inv_dt = datetime.fromisoformat(invoice_date_str)
        except Exception:
            try:
                inv_dt = datetime.strptime(
                    invoice_date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    inv_dt = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                except Exception:
                    inv_dt = None

        if inv_dt and (datetime.now() - inv_dt > timedelta(days=allow_days)):
            raise ValueError(
                f"Invoice can only be cancelled within {allow_days} days of creation.")

        # fetch invoice items (item_code, quantity)
        cur.execute(
            "SELECT item_code, quantity FROM invoice_item WHERE invoice_id = ?", (inv_id,))
        items = cur.fetchall()

        # start transaction
        conn.execute("BEGIN")
        # mark invoice cancelled
        now = datetime.now().isoformat(timespec="seconds")
        cur.execute("UPDATE invoice SET status = ?, updated_at = ? WHERE id = ?",
                    ("Cancelled", now, inv_id))

        # restore stock by inserting adjustment batches using same connection
        for item_code, qty in items:
            if qty is None or float(qty) == 0:
                continue
            # find item_id
            cur.execute(
                "SELECT id FROM item_master WHERE item_code = ?", (item_code,))
            r = cur.fetchone()
            if not r:
                # If item is missing from item_master we can't restore -> rollback
                raise ValueError(
                    f"Item code '{item_code}' not found in item_master; cannot restore stock.")

            item_id = r[0]
            # compute next batch_no for this item_id
            cur.execute(
                "SELECT IFNULL(MAX(batch_no), 0) FROM stock WHERE item_id = ?", (item_id,))
            max_batch = cur.fetchone()[0] or 0
            next_batch = int(max_batch) + 1

            # insert adjustment stock row (purchase_price 0.0)
            cur.execute("""
                INSERT INTO stock (item_id, batch_no, purchase_price, expiry_date, stock_type, quantity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, next_batch, 0.0, None, "adjustment", float(qty), now, now))

        conn.commit()
        return True
    except sqlite3.OperationalError:
        try:
            conn.rollback()
        except Exception:
            pass
        # re-raise so UI can detect "database is locked" and show appropriate message
        raise
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _ensure_date_string(d: Union[str, datetime, None]) -> str:
    """Return ISO date-time string for DB comparisons (date-only allowed)."""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.isoformat(timespec="seconds")
    # if date object
    return datetime(d.year, d.month, d.day).isoformat(timespec="seconds")


def get_sales_summary_range(start_date: Union[str, datetime, date],
                            end_date: Union[str, datetime, date]) -> Dict[str, float]:
    """
    Returns summary dict for the date range (inclusive):
      {
         'total_sales': sum of total_amount (without vat) for invoices (status != 'Cancelled'),
         'total_vat': sum of vat_amount,
         'net_total': sum of net_total,
         'total_purchase_value': sum of (purchase_price * quantity) for stock purchases in range
      }
    Date args may be 'YYYY-MM-DD' or datetime.
    """
    s_iso = _as_iso(start_date)
    e_iso = _as_iso(end_date, end_of_day=True)

    with closing(_connect()) as conn:
        cur = conn.cursor()
        # invoices
        cur.execute("""
            SELECT COALESCE(SUM(total_amount),0), COALESCE(SUM(vat_amount),0), COALESCE(SUM(net_total),0)
            FROM invoice
            WHERE invoice_date >= ? AND invoice_date <= ? AND (status IS NULL OR status != 'Cancelled')
        """, (s_iso, e_iso))
        total_amount, total_vat, net_total = cur.fetchone()

        # purchases in stock table (stock_type = 'purchase')
        cur.execute("""
            SELECT COALESCE(SUM(purchase_price * quantity), 0) FROM stock
            WHERE created_at >= ? AND created_at <= ? AND stock_type = 'purchase'
        """, (s_iso, e_iso))
        total_purchase_value = cur.fetchone()[0] or 0.0

        return {
            "total_sales": float(total_amount or 0.0),
            "total_vat": float(total_vat or 0.0),
            "net_total": float(net_total or 0.0),
            "total_purchase_value": float(total_purchase_value or 0.0)
        }


def _resolve_customer_id(conn, candidate):
    """
    If candidate is numeric (int), return it.
    If candidate is a customer_code (string), return matching customer.id or None.
    """
    if candidate is None:
        return None
    try:
        # already an integer id
        return int(candidate)
    except Exception:
        pass
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM customer WHERE customer_code = ? COLLATE NOCASE", (str(candidate),))
    row = cur.fetchone()
    return row[0] if row else None


def _resolve_salesman_id(conn, candidate):
    """Resolve salesman by emp_id or return numeric id if already int."""
    if candidate is None:
        return None
    try:
        return int(candidate)
    except Exception:
        pass
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM salesman WHERE emp_id = ? COLLATE NOCASE", (str(candidate),))
    row = cur.fetchone()
    return row[0] if row else None


def create_invoice(bill_to, ship_to, items, lpo_no="", discount=0, customer_id=None, salesman_id=None, outlet_id=None):
    """
    Create invoice atomically and reduce stock for non-free items.
    Accepts either numeric customer_id/salesman_id OR customer_code/salesman_emp_id strings.
    Returns invoice_no (string) on success.
    Raises ValueError with clear messages for missing/invalid references.
    """

    invoice_no = get_next_invoice_no()
    now = datetime.now().isoformat(timespec="seconds")

    # totals
    total_amount = 0.0
    total_vat = 0.0
    for it in items:
        qty = float(it.get("quantity", 0))
        rate = 0.0 if it.get("free", False) else float(it.get("rate", 0.0))
        sub = qty * rate
        vat_amt = sub * (float(it.get("vat_percentage", 0.0)) / 100.0)
        total_amount += sub
        total_vat += vat_amt

    taxable = max(0.0, total_amount - float(discount or 0.0))
    net_total = taxable + total_vat

    conn = _connect()
    try:
        cur = conn.cursor()
        conn.execute("BEGIN")
        # Resolve customer_id & salesman_id if needed
        resolved_customer_id = _resolve_customer_id(
            conn, customer_id or bill_to)
        resolved_salesman_id = _resolve_salesman_id(conn, salesman_id)

        # resolve outlet if provided (accept numeric id or code)
        resolved_outlet_id = None
        if outlet_id:
            resolved_outlet_id = _resolve_shipto_id(conn, outlet_id)
        else:
            # fallback: try to resolve ship_to param if it is outlet id/code
            resolved_outlet_id = _resolve_shipto_id(conn, ship_to)

        # If caller provided a customer_code and it wasn't found, raise clear error
        if (customer_id or bill_to) and resolved_customer_id is None:
            raise ValueError(
                f"Customer not found for identifier: {customer_id or bill_to}")

        if salesman_id and resolved_salesman_id is None:
            raise ValueError(
                f"Salesman not found for identifier: {salesman_id}")

        # Build bill/ship display strings (human-friendly) to store in invoice.bill_to / ship_to
        bill_display, ship_display = _build_bill_ship_display(
            conn, bill_to, ship_to, resolved_customer_id)

        cur.execute("""
        INSERT INTO invoice (
            invoice_no, invoice_date, customer_id, bill_to, ship_to, outlet_id, lpo_no,
            discount, total_amount, vat_amount, net_total, created_at, updated_at,
            balance, paid_amount, salesman_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_no, now, resolved_customer_id, bill_display, ship_display, resolved_outlet_id, lpo_no,
            float(discount or 0.0), total_amount, total_vat, net_total, now, now, net_total, 0.0, resolved_salesman_id
        ))

        invoice_id = cur.lastrowid

        # Insert items and reduce stock
        for idx, it in enumerate(items, start=1):
            qty = float(it.get("quantity", 0))
            rate = 0.0 if it.get("free", False) else float(it.get("rate", 0.0))
            sub = qty * rate
            vat_pct = float(it.get("vat_percentage", 0.0))
            vat_amt = sub * (vat_pct / 100.0)
            net_amount = sub + vat_amt

            cur.execute("""
            INSERT INTO invoice_item (
                invoice_id, serial_no, item_code, item_name, uom, per_box_qty,
                quantity, rate, sub_total, vat_percentage, vat_amount, net_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_id, idx, it.get("item_code"), it.get("item_name"),
                  it.get("uom"), it.get("per_box_qty", 1),
                  qty, rate, sub, vat_pct, vat_amt, net_amount))

            if not it.get("free", False):
                # reduce_stock_quantity expects item_code; keep same behaviour.
                reduce_stock_quantity(it.get("item_code"), qty, conn=conn)

        conn.commit()
        return invoice_no
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        # Make FK / resolution errors friendlier
        if isinstance(e, sqlite3.IntegrityError) and "FOREIGN KEY" in str(e).upper():
            raise ValueError(
                f"Foreign key constraint failed while creating invoice: {e}")
        raise
    finally:
        conn.close()


# initialize on import
init_invoice_db()
