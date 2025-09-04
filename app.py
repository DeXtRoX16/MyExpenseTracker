from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from datetime import datetime, date
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Change this to a random secret key

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change to your MySQL username
    'password': 'sH@01062006',  # Change to your MySQL password
    'database': 'expense_tracker',
    'auth_plugin': 'mysql_native_password'
}

def get_db_connection():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize database and create tables"""
    try:
        # Connect without specifying database to create it
        config_without_db = DB_CONFIG.copy()
        config_without_db.pop('database')
        conn = mysql.connector.connect(**config_without_db)
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS expense_tracker")
        cursor.close()
        conn.close()
        
        # Connect to the database and create tables
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Create categories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create expenses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    category_id INT,
                    description TEXT,
                    expense_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            ''')
            
            # Insert default categories
            default_categories = [
                'Food & Dining', 'Transportation', 'Shopping', 'Entertainment',
                'Bills & Utilities', 'Healthcare', 'Education', 'Travel', 'Other'
            ]
            
            for category in default_categories:
                cursor.execute(
                    "INSERT IGNORE INTO categories (name) VALUES (%s)",
                    (category,)
                )
            
            conn.commit()
            cursor.close()
            conn.close()
            print("Database initialized successfully!")
            
    except mysql.connector.Error as e:
        print(f"Database initialization error: {e}")

@app.route('/')
def index():
    """Home page showing recent expenses and summary"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed', 'error')
        return render_template('index.html', expenses=[], total_today=0, total_month=0)
    
    cursor = conn.cursor(dictionary=True)
    
    # Get recent expenses with category names
    cursor.execute('''
        SELECT e.*, c.name as category_name 
        FROM expenses e 
        LEFT JOIN categories c ON e.category_id = c.id 
        ORDER BY e.expense_date DESC, e.created_at DESC 
        LIMIT 10
    ''')
    recent_expenses = cursor.fetchall()
    
    # Get today's total
    today = datetime.now().date()
    cursor.execute('SELECT SUM(amount) as total FROM expenses WHERE expense_date = %s', (today,))
    total_today = cursor.fetchone()['total'] or 0
    
    # Get this month's total
    first_day_month = today.replace(day=1)
    cursor.execute(
        'SELECT SUM(amount) as total FROM expenses WHERE expense_date >= %s',
        (first_day_month,)
    )
    total_month = cursor.fetchone()['total'] or 0
    
    cursor.close()
    conn.close()
    
    return render_template('index.html', 
                        expenses=recent_expenses,
                        total_today=float(total_today),
                        total_month=float(total_month))

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    """Add new expense"""
    if request.method == 'POST':
        title = request.form['title']
        amount = request.form['amount']
        category_id = request.form['category_id']
        description = request.form.get('description', '')
        expense_date = request.form['expense_date']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO expenses (title, amount, category_id, description, expense_date)
                VALUES (%s, %s, %s, %s, %s)
            ''', (title, amount, category_id, description, expense_date))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Expense added successfully!', 'success')
        else:
            flash('Failed to add expense', 'error')
        
        return redirect(url_for('index'))
    
    # GET request - show form
    conn = get_db_connection()
    categories = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM categories ORDER BY name')
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('add_expense.html', categories=categories)

@app.route('/expenses')
def view_expenses():
    """View all expenses with filtering"""
    category_filter = request.args.get('category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    conn = get_db_connection()
    if not conn:
        return render_template('expenses.html', expenses=[], categories=[])
    
    cursor = conn.cursor(dictionary=True)
    
    # Build query with filters
    query = '''
        SELECT e.*, c.name as category_name 
        FROM expenses e 
        LEFT JOIN categories c ON e.category_id = c.id 
        WHERE 1=1
    '''
    params = []
    
    if category_filter:
        query += ' AND e.category_id = %s'
        params.append(category_filter)
    
    if date_from:
        query += ' AND e.expense_date >= %s'
        params.append(date_from)
        
    if date_to:
        query += ' AND e.expense_date <= %s'
        params.append(date_to)
    
    query += ' ORDER BY e.expense_date DESC, e.created_at DESC'
    
    cursor.execute(query, params)
    expenses = cursor.fetchall()
    
    # Get categories for filter dropdown
    cursor.execute('SELECT * FROM categories ORDER BY name')
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('expenses.html', 
                        expenses=expenses, 
                        categories=categories,
                        selected_category=category_filter,
                        date_from=date_from,
                        date_to=date_to)

@app.route('/delete_expense/<int:expense_id>')
def delete_expense(expense_id):
    """Delete an expense"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = %s', (expense_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Expense deleted successfully!', 'success')
    else:
        flash('Failed to delete expense', 'error')
    
    return redirect(request.referrer or url_for('index'))

@app.route('/analytics')
def analytics():
    """Analytics page with charts and statistics"""
    conn = get_db_connection()
    if not conn:
        return render_template('analytics.html')
    
    cursor = conn.cursor(dictionary=True)
    
    # Monthly spending for the last 6 months
    cursor.execute('''
        SELECT DATE_FORMAT(expense_date, '%Y-%m') as month,
            SUM(amount) as total
        FROM expenses
        WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
        ORDER BY month
    ''')
    monthly_data = cursor.fetchall()
    
    # Category breakdown
    cursor.execute('''
        SELECT c.name, SUM(e.amount) as total, COUNT(e.id) as count
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        GROUP BY c.id, c.name
        ORDER BY total DESC
    ''')
    category_data = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('analytics.html',
                        monthly_data=monthly_data,
                        category_data=category_data)

@app.route('/api/monthly_data')
def api_monthly_data():
    """API endpoint for monthly data"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT DATE_FORMAT(expense_date, '%Y-%m') as month,
            SUM(amount) as total
        FROM expenses
        WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
        ORDER BY month
    ''')
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert Decimal to float for JSON serialization
    for item in data:
        item['total'] = float(item['total'])
    
    return jsonify(data)

@app.route('/api/category_data')
def api_category_data():
    """API endpoint for category data"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT c.name, SUM(e.amount) as total
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        GROUP BY c.id, c.name
        ORDER BY total DESC
    ''')
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert Decimal to float for JSON serialization
    for item in data:
        item['total'] = float(item['total'])
    
    return jsonify(data)

if __name__ == '__main__':
    init_database()
    app.run(debug=True)