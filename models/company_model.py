import sqlite3
import os

DB_FILE = "data/database.db"


def initialize_company_profile_table():
    """
    Create the company_profile table if it does not exist.
    Add missing columns if table already exists.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS company_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            gst_no TEXT,
            address TEXT,
            email TEXT,
            phone TEXT,
            logo_path TEXT
        )
    ''')

    # Check existing columns
    c.execute("PRAGMA table_info(company_profile)")
    existing_columns = [col[1] for col in c.fetchall()]

    # Add missing columns dynamically
    if "phone" not in existing_columns:
        c.execute("ALTER TABLE company_profile ADD COLUMN phone TEXT DEFAULT ''")
    if "logo_path" not in existing_columns:
        c.execute(
            "ALTER TABLE company_profile ADD COLUMN logo_path TEXT DEFAULT ''")

    # Insert default row if table is empty
    c.execute('SELECT COUNT(*) FROM company_profile')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO company_profile (name, gst_no, address, email, phone, logo_path)
            VALUES ("", "", "", "", "", "")
        ''')

    conn.commit()
    conn.close()


def get_company_profile():
    """
    Retrieve company profile data as a tuple:
    (name, gst_no, address, email, phone, logo_path)
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'SELECT name, gst_no, address, email, phone, logo_path FROM company_profile LIMIT 1')
    row = c.fetchone()
    conn.close()
    return row


def save_company_profile(name, gst_no, address, email, phone, logo_path):
    """
    Update the company profile details in the database.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE company_profile
        SET name=?, gst_no=?, address=?, email=?, phone=?, logo_path=?
        WHERE id=1
    ''', (name, gst_no, address, email, phone, logo_path))
    conn.commit()
    conn.close()
