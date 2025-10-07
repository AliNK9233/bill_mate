import sqlite3

DB_FILE = "data/database.db"


def initialize_company_profile_table():
    """
    Create company_profile table if it doesn't exist
    and add default placeholder row.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS company_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'Rayani Engineering',
            gst_no TEXT DEFAULT 'Enter GST Number',
            address TEXT DEFAULT 'Enter Address',
            phone1 TEXT DEFAULT 'Enter Phone 1',
            phone2 TEXT DEFAULT 'Enter Phone 2',
            email TEXT DEFAULT 'Enter Email',
            website TEXT DEFAULT 'Enter Website',
            bank_name TEXT DEFAULT 'Enter Bank Name',
            bank_account TEXT DEFAULT 'Enter Account No',
            ifsc_code TEXT DEFAULT 'Enter IFSC Code',
            branch_address TEXT DEFAULT 'Enter Branch Address',
            logo_path TEXT DEFAULT ''
        )
    """)
    # Insert default row if table is empty
    c.execute("SELECT COUNT(*) FROM company_profile")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO company_profile
            (name, gst_no, address, phone1, phone2, email, website,
             bank_name, bank_account, ifsc_code, branch_address, logo_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Rayani Engineering", "Enter GST Number", "Enter Address",
            "Enter Phone 1", "Enter Phone 2", "Enter Email",
            "Enter Website", "Enter Bank Name", "Enter Account No",
            "Enter IFSC Code", "Enter Branch Address", ""
        ))
    conn.commit()
    conn.close()


def get_company_profile():
    """
    Fetch the company profile (only 1 row expected).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM company_profile LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "gst_no": row[2],
            "address": row[3],
            "phone1": row[4],
            "phone2": row[5],
            "email": row[6],
            "website": row[7],
            "bank_name": row[8],
            "bank_account": row[9],
            "ifsc_code": row[10],
            "branch_address": row[11],
            "logo_path": row[12]
        }
    else:
        # Should never happen because we insert default row
        return {}


def save_company_profile(profile_data):
    """
    Save updates to the company profile (update single row).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        UPDATE company_profile
        SET gst_no = ?, address = ?, phone1 = ?, phone2 = ?,
            email = ?, website = ?, bank_name = ?, bank_account = ?,
            ifsc_code = ?, branch_address = ?, logo_path = ?
        WHERE id = ?
    """, (
        profile_data["gst_no"], profile_data["address"], profile_data["phone1"],
        profile_data["phone2"], profile_data["email"], profile_data["website"],
        profile_data["bank_name"], profile_data["bank_account"],
        profile_data["ifsc_code"], profile_data["branch_address"],
        profile_data["logo_path"], profile_data["id"]
    ))
    conn.commit()
    conn.close()
