# scripts/migrate_add_cancel_reason.py
import sqlite3
import os
DB = "data/database.db"


def column_exists(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())


os.makedirs(os.path.dirname(DB), exist_ok=True)

with sqlite3.connect(DB) as conn:
    cur = conn.cursor()

    # Add cancel_reason column if missing
    if not column_exists(conn, "invoice", "cancel_reason"):
        print("Adding column invoice.cancel_reason ...")
        cur.execute(
            "ALTER TABLE invoice ADD COLUMN cancel_reason TEXT DEFAULT NULL")
    else:
        print("invoice.cancel_reason already exists")

    # Example: keep outlet_id migration alongside if you want
    if not column_exists(conn, "invoice", "outlet_id"):
        print("Adding column invoice.outlet_id ...")
        cur.execute(
            "ALTER TABLE invoice ADD COLUMN outlet_id INTEGER DEFAULT NULL")
    else:
        print("invoice.outlet_id already exists")

    conn.commit()

print("Migration finished.")
