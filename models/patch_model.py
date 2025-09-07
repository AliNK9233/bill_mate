# scripts/migrate_add_outlet_id.py
import sqlite3
DB = "data/database.db"


def column_exists(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())


with sqlite3.connect(DB) as conn:
    cur = conn.cursor()
    if not column_exists(conn, "invoice", "outlet_id"):
        print("Adding column invoice.outlet_id ...")
        cur.execute("ALTER TABLE invoice ADD COLUMN outlet_id INTEGER")
    else:
        print("invoice.outlet_id already exists")
    conn.commit()
print("Done.")
