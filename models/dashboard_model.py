import sqlite3
from models.stock_model import DB_FILE
from datetime import datetime, timedelta

# Sales Metrics


def get_total_sales(year):
    """
    Get the total sum of all invoice amounts for a given year.
    Returns: Float representing total sales or 0.0 if no sales.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE strftime("%Y", date)=?', (year,))
    result = c.fetchone()[0]
    conn.close()
    return result


def get_total_customers(year):
    """
    Get the total number of customers who made purchases in a given year.
    Returns: Integer count of customers or 0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT COALESCE(COUNT(DISTINCT customer_id), 0) FROM invoices
        WHERE strftime("%Y", date)=?
    ''', (year,))
    result = c.fetchone()[0]
    conn.close()
    return result


def get_total_pending_balance(year):
    """
    Get the total pending balance from invoices with positive balance for a given year.
    Returns: Float representing total pending balance or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT COALESCE(SUM(balance), 0) FROM invoices
        WHERE balance > 0 AND strftime("%Y", date)=?
    ''', (year,))
    result = c.fetchone()[0]
    conn.close()
    return result

# Customer Analytics


def get_top_customers(year):
    """
    Get the top 5 customers by total sales amount for a given year.
    Returns: List of tuples (name, phone, total_sales).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT c.name, c.phone, SUM(i.total_amount) as total_sales
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        WHERE strftime("%Y", i.date)=?
        GROUP BY c.id
        ORDER BY total_sales DESC
        LIMIT 5
    ''', (year,))
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


def get_total_jobwork(year):
    """
    Get total amount for all jobwork invoices for a given year.
    Returns: Float representing total jobwork amount or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'SELECT COALESCE(SUM(total_amount), 0) FROM jobwork_invoices WHERE strftime("%Y", date)=?', (year,))
    result = c.fetchone()[0]
    conn.close()
    return result


def get_total_jobwork_pending(year):
    """
    Get total pending balance for jobwork invoices for a given year.
    Returns: Float representing total pending jobwork balance or 0.0 if none.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT COALESCE(SUM(balance), 0) FROM jobwork_invoices
        WHERE balance > 0 AND strftime("%Y", date)=?
    ''', (year,))
    result = c.fetchone()[0]
    conn.close()
    return result


def get_total_purchases(year):
    """
    Get total purchase value for a given year.
    Sums purchase_price * quantity from stock_batches for the year.
    Returns: Float (0.0 if no purchases).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        '''
        SELECT COALESCE(SUM(purchase_price * quantity), 0)
        FROM stock_batches
        WHERE purchase_date IS NOT NULL
          AND strftime('%Y', purchase_date) = ?
        ''',
        (year,)
    )
    result = c.fetchone()[0] or 0.0
    conn.close()
    return result


def get_monthly_sales_jobwork(year):
    """
    Get monthly sales and jobwork totals for the selected year.
    Returns: List of tuples (month_name, sales, jobwork) for Jan–Dec.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch monthly data from invoices
    c.execute('''
        SELECT strftime('%m', date) as month_num,
               SUM(total_amount) as sales,
               (SELECT SUM(total_amount)
                FROM jobwork_invoices
                WHERE strftime('%m', date)=strftime('%m', invoices.date)
                  AND strftime('%Y', date)=?) as jobwork
        FROM invoices
        WHERE strftime('%Y', date)=?
        GROUP BY month_num
    ''', (year, year))
    rows = c.fetchall()
    conn.close()

    # Build a dictionary from fetched data
    data_dict = {int(row[0]): (row[1] or 0, row[2] or 0) for row in rows}

    # Prepare full 12 months with zero-filled data if missing
    result = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for month_num in range(1, 13):
        sales, jobwork = data_dict.get(month_num, (0, 0))
        result.append((f"{month_names[month_num - 1]} {year}", sales, jobwork))

    return result


def get_available_invoice_years():
    """
    Get a list of distinct years from the invoices table.
    Returns: List of years (strings).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'SELECT DISTINCT strftime("%Y", date) FROM invoices ORDER BY strftime("%Y", date) DESC')
    years = [row[0] for row in c.fetchall()]
    conn.close()
    return years
