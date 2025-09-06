#!/usr/bin/env python3
"""
Migration: add missing columns to invoice table if absent.

Usage:
    python migrations/upgrade_invoice_schema.py
"""

import sqlite3
import os
import sys

DB_FILE = "data/database.db"

EXPECTED_COLUMNS = {
    # column_name: SQL fragment for ADD COLUMN (SQLite supports simple DEFAULT and NULL)
    "customer_id": "INTEGER",
    "balance": "REAL DEFAULT 0",
    "paid_amount": "REAL DEFAULT 0",
    "remarks": "TEXT",
    # If you expect other columns that might be missing, list them here.
    # e.g. "salesman_id": "INTEGER"
}

if not os.path.exists(DB_FILE):
    print(f"Database file not found: {DB_FILE}")
    sys.exit(1)


def get_table_columns(conn, table_name):
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    cols = [r[1] for r in cur.fetchall()]  # name is second column
    return cols


def add_column(conn, table, column_name, add_sql):
    sql = f"ALTER TABLE {table} ADD COLUMN {column_name} {add_sql}"
    print("Executing:", sql)
    conn.execute(sql)


def migrate():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cur = conn.cursor()

    # Ensure invoice table exists
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='invoice'")
    if not cur.fetchone():
        print("No 'invoice' table found. Nothing to migrate.")
        conn.close()
        return

    existing = get_table_columns(conn, "invoice")
    added = []

    try:
        for col, definition in EXPECTED_COLUMNS.items():
            if col not in existing:
                add_column(conn, "invoice", col, definition)
                added.append(col)

        if added:
            conn.commit()
            print("Migration complete. Added columns:", ", ".join(added))
        else:
            print("No migration needed. All expected columns present.")
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
