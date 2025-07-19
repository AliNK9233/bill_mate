import sqlite3
import os

# Path to your DB
DB_FILE = "data/database.db"


def migrate_company_profile():
    """
    Drops and recreates company_profile table with new structure
    and inserts a default row.
    """
    if not os.path.exists(DB_FILE):
        print(f"❌ Database file not found at {DB_FILE}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Drop old table
    print("⚠️ Dropping existing company_profile table (if any)...")
    cursor.execute("DROP TABLE IF EXISTS company_profile")

    # # Create new table
    # print("✅ Creating new company_profile table...")
    # cursor.execute('''
    #     CREATE TABLE company_profile (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         name TEXT NOT NULL,
    #         gst_no TEXT,
    #         address TEXT,
    #         phone1 TEXT,
    #         phone2 TEXT,
    #         email TEXT,
    #         website TEXT,
    #         logo_path TEXT,
    #         admin_password TEXT,
    #         bank_name TEXT,
    #         bank_account TEXT,
    #         ifsc_code TEXT,
    #         branch_address TEXT
    #     )
    # ''')

    # # Insert default row
    # print("✅ Inserting default company profile...")
    # cursor.execute('''
    #     INSERT INTO company_profile
    #     (name, gst_no, address, phone1, phone2, email, website,
    #      logo_path, admin_password, bank_name, bank_account, ifsc_code, branch_address)
    #     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    # ''', (
    #     "Rayani Tech Pvt Ltd",  # Company Name
    #     "22ABCDE1234F1Z5",    # GST No
    #     "123 Example Street, City, State - 123456",
    #     "+91-9876543210",     # Phone 1
    #     "+91-9123456789",     # Phone 2
    #     "info@example.com",   # Email
    #     "www.example.com",    # Website
    #     "data\logos\rayani_logo.png",                   # Logo Path
    #     "admin@123",          # Admin Password
    #     "HDFC Bank",          # Bank Name
    #     "123456789012",       # Bank Account
    #     "HDFC0001234",        # IFSC Code
    #     "HDFC Main Branch, City"
    # ))

    conn.commit()
    conn.close()
    print("🎉 Migration complete!")


if __name__ == "__main__":
    migrate_company_profile()
