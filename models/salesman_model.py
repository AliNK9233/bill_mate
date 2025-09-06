import sqlite3
import os
from datetime import datetime

DB_FILE = "data/database.db"


def init_salesman_db():
    """
    Create salesman table if it doesn't exist
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS salesman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        remarks TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()


def add_salesman(emp_id, name, phone=None, email=None, remarks=None):
    """
    Add new salesman entry
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat(timespec='seconds')
    cursor.execute("""
        INSERT INTO salesman (emp_id, name, phone, email, remarks, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (emp_id, name, phone, email, remarks, now, now))
    conn.commit()
    conn.close()


def get_all_salesmen():
    """
    Get all salesmen
    Returns list of tuples: (emp_id, name, phone, email, remarks)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT emp_id, name, phone, email, remarks FROM salesman ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_salesman(emp_id, **kwargs):
    """
    Update salesman by emp_id
    Example: update_salesman("EMP001", phone="1234567890")
    """
    if not kwargs:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    values.append(emp_id)

    cursor.execute(f"UPDATE salesman SET {fields}, updated_at = ? WHERE emp_id = ?",
                   values[:-1] + [datetime.now().isoformat(), emp_id])
    conn.commit()
    conn.close()


def delete_salesman(emp_id):
    """
    Delete salesman by emp_id
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM salesman WHERE emp_id = ?", (emp_id,))
    conn.commit()
    conn.close()


# Initialize table when imported
init_salesman_db()
