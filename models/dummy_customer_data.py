import sqlite3
from models.stock_model import DB_FILE
from models.invoice_model import initialize_invoice_db

# Ensure tables exist
initialize_invoice_db()

# Dummy customers
dummy_customers = [
    ("Rahul Sharma", "9876543210", "Bangalore", 1200.0),
    ("Priya Menon", "9123456789", "Chennai", 0.0),
    ("Kiran Kumar", "9988776655", "Hyderabad", 550.0),
    ("Fatima Noor", "9012345678", "Kochi", 0.0),
    ("Ravi Verma", "9345678901", "Delhi", 300.0)
]

# Insert customers
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

for name, phone, address, balance in dummy_customers:
    c.execute('''
        INSERT INTO customers (name, phone, address, outstanding_balance)
        VALUES (?, ?, ?, ?)
    ''', (name, phone, address, balance))

conn.commit()
conn.close()

print("✅ Dummy customer data inserted successfully!")
