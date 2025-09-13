# --- add this to your migration script alongside migrate_to_v1 ---
def migrate_to_v2(conn):
    """
    Create customers, invoices, invoice_items, payments, jobwork and company_profile
    tables referenced by your model files. Idempotent: uses IF NOT EXISTS and
    INSERT OR IGNORE patterns where appropriate.
    """
    # customers
    conn.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        opening_balance REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # invoices
    conn.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT NOT NULL UNIQUE,
        customer_id INTEGER,
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        subtotal REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        total_amount REAL DEFAULT 0,
        paid_amount REAL DEFAULT 0,
        balance REAL DEFAULT 0,
        payment_method TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
    );
    """)

    # invoice items
    conn.execute("""
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        stock_id INTEGER,
        description TEXT,
        quantity REAL DEFAULT 0,
        unit_price REAL DEFAULT 0,
        tax_percent REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        total_amount REAL DEFAULT 0,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (stock_id) REFERENCES stock(id) ON DELETE SET NULL
    );
    """)

    # payments (for invoices / customer payments)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        customer_id INTEGER,
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        amount REAL NOT NULL,
        method TEXT,
        reference TEXT,
        notes TEXT,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
    );
    """)

    # jobwork tables (basic)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS jobworks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jw_no TEXT NOT NULL UNIQUE,
        customer_id INTEGER,
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        description TEXT,
        total_amount REAL DEFAULT 0,
        status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS jobwork_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jobwork_id INTEGER,
        description TEXT,
        qty REAL DEFAULT 0,
        rate REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        FOREIGN KEY (jobwork_id) REFERENCES jobworks(id) ON DELETE CASCADE
    );
    """)

    # company profile (single row config table)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        address TEXT,
        phone TEXT,
        email TEXT,
        gstin TEXT,
        footer_note TEXT,
        logo_path TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # helpful indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invoices_invoice_no ON invoices(invoice_no);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invoices_customer_id ON invoices(customer_id);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobworks_jw_no ON jobworks(jw_no);")
