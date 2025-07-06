from models.stock_model import get_stock_with_batches
from models.stock_model import initialize_db, add_stock_item, add_stock_batch

# Initialize DB and create tables
initialize_db()

# Add stock items with HSN and GST %
stock_items = [
    # (name, code, unit, hsn_code, gst_percent)
    ("Aldrop 1/2*9", "ALD001", "Pcs", "8302", 18.0),
    ("3/8*6 Aldrop set", "ALD002", "Pcs", "8302", 18.0),
    ("Aldrop 5/8*14", "ALD003", "Pcs", "8302", 18.0),
    ("Tower Bolt 1/2*6", "TWB001", "Pcs", "8302", 18.0),
    ("Tower Bolt 1/2*10", "TWB002", "Pcs", "8302", 18.0),
    ("Dummy washer (3½)", "DWS001", "Kg", "7318", 18.0),
    ("Tower Bolt 5/8X14", "TWB003", "Pcs", "8302", 18.0),
]

# Insert stock items
for name, code, unit, hsn_code, gst_percent in stock_items:
    try:
        add_stock_item(name, code, unit, hsn_code, gst_percent)
        print(
            f"✅ Added Stock Item: {name} (HSN: {hsn_code}, GST: {gst_percent}%)")
    except Exception as e:
        print(f"⚠️ Skipping {name}: {e}")

# Add batches for each stock item
all_data = get_stock_with_batches()
for row in all_data:
    stock_id = row[0]
    purchase_price = 50.0  # Use default purchase price for testing
    selling_price = 60.0   # Default selling price
    quantity = 100         # Default quantity

    try:
        add_stock_batch(stock_id, purchase_price, selling_price, quantity)
        print(
            f"✅ Added Batch for {row[1]}: Qty={quantity}, Purchase ₹{purchase_price}, Selling ₹{selling_price}")
    except Exception as e:
        print(f"⚠️ Skipping Batch for {row[1]}: {e}")
