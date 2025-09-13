#!/usr/bin/env python3
# migrate_delivery_tables.py
import sqlite3
import os
import sys

DB_FILE = "data/database.db"


def ensure_db_exists():
    if not os.path.exists(DB_FILE):
        print(f"ERROR: database not found at {DB_FILE}")
        sys.exit(1)


def table_exists(conn, name):
    c = conn.cursor()
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return c.fetchone() is not None


def create_tables_if_missing():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if not table_exists(conn, "delivery_challan"):
        print("Creating table: delivery_challan")
        c.execute("""
        CREATE TABLE IF NOT EXISTS delivery_challan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challan_no TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            company_profile_id INTEGER,
            to_address TEXT,
            to_gst_no TEXT,
            transporter_name TEXT,
            vehicle_no TEXT,
            delivery_location TEXT,
            description TEXT,
            related_invoice_no TEXT,
            total_qty REAL DEFAULT 0,
            created_by TEXT
        );
        """)
    else:
        print("Table delivery_challan already exists - skipping")

    if not table_exists(conn, "delivery_items"):
        print("Creating table: delivery_items")
        c.execute("""
        CREATE TABLE IF NOT EXISTS delivery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challan_id INTEGER NOT NULL,
            item_code TEXT,
            item_name TEXT NOT NULL,
            hsn_code TEXT,
            qty REAL DEFAULT 0,
            unit TEXT,
            FOREIGN KEY (challan_id) REFERENCES delivery_challan(id) ON DELETE CASCADE
        );
        """)
    else:
        print("Table delivery_items already exists - skipping")

    if not table_exists(conn, "dc_description_suggestions"):
        print("Creating table: dc_description_suggestions")
        c.execute("""
        CREATE TABLE IF NOT EXISTS dc_description_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT UNIQUE NOT NULL,
            usage_count INTEGER DEFAULT 1,
            last_used TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
    else:
        print("Table dc_description_suggestions already exists - skipping")

    # Indexes (idempotent)
    print("Ensuring indexes...")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_dc_challan_no ON delivery_challan(challan_no);")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_dc_created_at ON delivery_challan(created_at);")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_di_challan_id ON delivery_items(challan_id);")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    ensure_db_exists()
    create_tables_if_missing()
