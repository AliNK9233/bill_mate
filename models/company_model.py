import sqlite3
import os

DB_FILE = "data/database.db"


def init_db():
    """
    Initialize the company_profile table and add a default row if not exists.
    """
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),  -- enforce only one row
        company_name TEXT,
        trn_no TEXT,
        address_line1 TEXT,
        address_line2 TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        phone1 TEXT,
        phone2 TEXT,
        email TEXT,
        website TEXT,
        bank_name TEXT,
        account_name TEXT,
        account_number TEXT,
        iban TEXT,
        swift_code TEXT,
        logo_path TEXT
    )
    """)

    # Insert default row if not present
    cursor.execute("SELECT COUNT(*) FROM company_profile")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO company_profile (
            id, company_name, trn_no, address_line1, address_line2, city, state, country,
            phone1, phone2, email, website,
            bank_name, account_name, account_number, iban, swift_code, logo_path
        ) VALUES (
            1, 'Your Company Name', 'TRN123456', 'Address line 1', 'Address line 2',
            'Dubai', 'Dubai', 'UAE',
            '+971-0000000', '', 'info@example.com', 'www.example.com',
            'Bank Name', 'Account Holder', '000000000', 'AE000000000000000000000',
            'SWIFT1234', 'path/to/logo.png'
        )
        """)
        conn.commit()

    conn.close()


def get_company_profile():
    """
    Fetch the single company profile.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row


def save_company_profile(data: dict):
    """
    Update the company profile.
    data = {
        'company_name': ..., 'trn_no': ..., 'address_line1': ..., ...
    }
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    fields = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values())
    values.append(1)  # where id = 1

    cursor.execute(f"UPDATE company_profile SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def update_logo(path: str):
    """
    Update only the logo path.
    """
    save_company_profile({"logo_path": path})


# --- Run once to initialize ---
if __name__ == "__main__":
    init_db()
    print(get_company_profile())
