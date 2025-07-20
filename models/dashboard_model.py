import sqlite3
from models.stock_model import DB_FILE
from datetime import datetime, timedelta

# Sales Metrics


def get_total_sales():
    """
    Get the total sum of all invoice amounts.
    Returns: Float representing total sales or 0.0 if no sales.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(total_amount) FROM invoices')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


def get_total_customers():
    """
    Get the total number of customers.
    Returns: Integer count of customers or 0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM customers')
    result = c.fetchone()[0]
    conn.close()
    return result or 0


def get_total_pending_balance():
    """
    Get the total pending balance from invoices with positive balance.
    Returns: Float representing total pending balance or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(balance) FROM invoices WHERE balance > 0')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


# Customer Analytics
def get_top_customers():
    """
    Get the top 5 customers by total sales amount.
    Returns: List of tuples (name, phone, total_sales).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT c.name, c.phone, SUM(i.total_amount) as total_sales
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        GROUP BY c.id
        ORDER BY total_sales DESC
        LIMIT 5
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


# Inventory Management
def get_low_stock_items():
    """
    Get items with total quantity <= 10 across all batches.
    Returns: List of tuples (name, code, total_qty).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT s.name, s.code, SUM(b.available_qty) as total_qty
        FROM stock s
        JOIN stock_batches b ON s.id = b.stock_id
        GROUP BY s.id
        HAVING total_qty <= 10
        ORDER BY total_qty ASC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


# Job Work Metrics
def get_total_jobwork():
    """
    Get total amount for all jobwork invoices.
    Returns: Float representing total jobwork amount or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(total_amount) FROM jobwork_invoices')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


def get_total_jobwork_pending():
    """
    Get total pending balance for jobwork invoices.
    Returns: Float representing total pending jobwork balance or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT SUM(balance) FROM jobwork_invoices WHERE balance > 0')
    result = c.fetchone()[0]
    conn.close()
    return result or 0.0


def get_monthly_sales_jobwork():
    """
    Get monthly sales and jobwork totals for the last 6 months.
    Returns: List of tuples (month, sales, jobwork) in chronological order.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Calculate the date 6 months ago from July 20, 2025
    end_date = datetime(2025, 7, 20)
    start_date = end_date - timedelta(days=6*30)  # Approximate 6 months
    c.execute('''
        SELECT strftime('%b %Y', date) as month,
               SUM(CASE WHEN total_amount IS NOT NULL THEN total_amount ELSE 0 END) as sales,
               (SELECT SUM(total_amount)
                FROM jobwork_invoices
                WHERE strftime('%m%Y', date) = strftime('%m%Y', invoices.date)
               ) as jobwork
        FROM invoices
        WHERE date BETWEEN ? AND ?
        GROUP BY month
        ORDER BY date ASC
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    rows = c.fetchall()
    conn.close()
    return rows
