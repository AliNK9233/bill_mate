import sqlite3

DB_FILE = "data/database.db"


def migrate_jobwork_tables():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    print("🔄 Starting migration...")

    # 🚨 Drop old tables if they exist
    c.execute("DROP TABLE IF EXISTS jobwork_items")
    c.execute("DROP TABLE IF EXISTS jobwork_invoices")

    print("🗑️ Dropped old jobwork tables.")

    # ✅ Recreate jobwork_invoices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobwork_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            customer_id INTEGER,
            billing_type TEXT, -- Normal Bill or GST Bill
            subtotal REAL,
            tax_amount REAL,
            total_amount REAL,
            paid_amount REAL,
            balance REAL,
            payment_method TEXT,
            status TEXT,  -- Paid, Partial, Unpaid
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    print("✅ Created jobwork_invoices table.")

    # ✅ Recreate jobwork_items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobwork_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            description TEXT,
            amount REAL,
            FOREIGN KEY (invoice_id) REFERENCES jobwork_invoices(id)
        )
    ''')
    print("✅ Created jobwork_items table.")

    conn.commit()
    conn.close()
    print("🎉 Migration completed successfully!")


# Run the migration
migrate_jobwork_tables()
