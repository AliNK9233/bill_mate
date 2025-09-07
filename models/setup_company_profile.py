# scripts/setup_company_profile.py
import sqlite3
import os
from datetime import datetime

DB_FILE = "data/database.db"

DEFAULT_PROFILE = {
    "company_name": "RIZQ AL EZZAT TRADING",
    "trn_no": "TRN123456",                # TRN / GST number
    "address_line1": "Address line 1",
    "address_line2": "P.O. Box : 1072",
    "city": "Dubai",
    "state": "Dubai",
    "country": "UAE",
    "phone1": "+97 503319123",
    "phone2": "",
    "email": "rizq.alezzat@gmail.com",
    "website": "www.rizqalezzat.com",
    "bank_name": "Bank Name",
    "account_name": "Account Holder",
    "account_number": "000000000",
    "iban": "AE000000000000000000000",
    "swift_code": "SWIFT1234",
    "logo_path": "data/logos/c_logo.png",
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "updated_at": datetime.now().isoformat(timespec="seconds"),
}


def ensure_db_dir():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


def init_db_and_default():
    """
    Create company_profile table if missing and insert a default row
    (id = 1) if table is empty.
    """
    ensure_db_dir()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
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
        logo_path TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # If the table is empty, insert default row (id = 1)
    cursor.execute("SELECT COUNT(*) FROM company_profile")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("""
        INSERT INTO company_profile (
            id, company_name, trn_no, address_line1, address_line2, city, state, country,
            phone1, phone2, email, website, bank_name, account_name, account_number,
            iban, swift_code, logo_path, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            DEFAULT_PROFILE["company_name"],
            DEFAULT_PROFILE["trn_no"],
            DEFAULT_PROFILE["address_line1"],
            DEFAULT_PROFILE["address_line2"],
            DEFAULT_PROFILE["city"],
            DEFAULT_PROFILE["state"],
            DEFAULT_PROFILE["country"],
            DEFAULT_PROFILE["phone1"],
            DEFAULT_PROFILE["phone2"],
            DEFAULT_PROFILE["email"],
            DEFAULT_PROFILE["website"],
            DEFAULT_PROFILE["bank_name"],
            DEFAULT_PROFILE["account_name"],
            DEFAULT_PROFILE["account_number"],
            DEFAULT_PROFILE["iban"],
            DEFAULT_PROFILE["swift_code"],
            DEFAULT_PROFILE["logo_path"],
            DEFAULT_PROFILE["created_at"],
            DEFAULT_PROFILE["updated_at"],
        ))
        conn.commit()
        print("✅ Inserted default company_profile row (id=1).")
    else:
        print("ℹ️ company_profile table already has data (no default inserted).")

    conn.close()


def get_company_profile_dict():
    """
    Return the company profile as a dictionary with convenient aliases.
    Aliases map to keys your UI/PDF code often expects (e.g. 'name','gst_no').
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    cols = [
        "id", "company_name", "trn_no", "address_line1", "address_line2",
        "city", "state", "country", "phone1", "phone2",
        "email", "website", "bank_name", "account_name",
        "account_number", "iban", "swift_code", "logo_path",
        "created_at", "updated_at"
    ]
    data = dict(zip(cols, row))

    # Add a few convenient derived fields / aliases expected by other code:
    data_alias = {
        **data,
        "name": data.get("company_name"),
        "gst_no": data.get("trn_no"),           # alias
        "address": ", ".join(filter(None, [data.get("address_line1"), data.get("address_line2"), data.get("city"), data.get("state"), data.get("country")])),
        "phone": data.get("phone1") or data.get("phone2"),
    }
    return data_alias


if __name__ == "__main__":
    init_db_and_default()
    profile = get_company_profile_dict()
    print("Loaded company profile:")
    for k, v in profile.items():
        print(f"  {k}: {v}")
