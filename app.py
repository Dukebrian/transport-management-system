import os
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "transport_system_secure_session_token_key"

# Dynamic file system routing path mapping (Crucial for total offline mode & Render platform)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "transport.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    
    # 1. Saccos Operator Table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS saccos (
        sacco_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sacco_name TEXT NOT NULL UNIQUE,
        contact_number TEXT
    );""")
    
    # 2. Users System Credentials Table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        id_number TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('admin', 'passenger')) NOT NULL
    );""")
    
    # 3. Transit Routes Grid Corridor Table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS routes (
        route_id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_name TEXT NOT NULL,
        distance REAL NOT NULL,
        monthly_fare REAL NOT NULL
    );""")
    
    # 4. Fleet Vehicles Table (Linked directly to Saccos and Routes)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS buses (
        bus_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT NOT NULL UNIQUE,
        capacity INTEGER NOT NULL,
        route_id INTEGER,
        sacco_id INTEGER,
        FOREIGN KEY (route_id) REFERENCES routes (route_id) ON DELETE SET NULL,
        FOREIGN KEY (sacco_id) REFERENCES saccos (sacco_id) ON DELETE SET NULL
    );""")
    
    # 5. Commuter Subscriptions Management Ledger
    conn.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
        passenger_id INTEGER,
        route_id INTEGER,
        status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
        FOREIGN KEY (passenger_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (route_id) REFERENCES routes(route_id) ON DELETE CASCADE
    );""")

    # 6. Financial Billing Statements Invoices Table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        passenger_id INTEGER,
        subscription_id INTEGER,
        amount REAL NOT NULL,
        month TEXT NOT NULL,
        status TEXT CHECK(status IN ('paid', 'unpaid')) DEFAULT 'unpaid',
        payment_date TEXT,
        FOREIGN KEY (passenger_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id) ON DELETE CASCADE
    );""")
    
    # Bootstrap default public transport Sacco operators if empty
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM saccos")
    if cursor.fetchone()[0] == 0:
        default_saccos = [("Super Metro",), ("Metro Trans",), ("Lopha Sacco",), ("Latema Sacco",), ("Zuri Cabs",)]
        cursor.executemany("INSERT INTO saccos (sacco_name) VALUES (?)", default_saccos)
        
    # Bootstrap default professional system admin account configuration profile
    cursor.execute("SELECT * FROM users WHERE role='admin'")
    if not cursor.fetchone():
        hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (name, phone, id_number, password, role) VALUES (?, ?, ?, ?, ?)",
            ("System Admin", "0000000000", "ADMIN001", hashed_pw, "admin")
        )
        
    conn.commit()
    conn.close()

# --- SYSTEM DASHBOARD GATEWAY MIDDLEWARE CONTROLLERS ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_number = request.form['id_number']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE id_number=? AND password=?", (id_number, hashed)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('passenger_dashboard'))
        else:
            flash("Invalid ID Number or Password credentials.", "error")
            
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    phone = request.form['phone']
    id_number = request.form['id_number']
    password = request.form['password']
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, phone, id_number, password, role) VALUES (?, ?, ?, ?, 'passenger')",
            (name, phone, id_number, hashed)
        )
        conn.commit()
        flash("Registration successful! Please log in below.", "success")
    except sqlite3.IntegrityError:
        flash("Error: Phone number or ID number already registered.", "error")
    finally:
        conn.close()
        
    return redirect(url_for('login'))

# --- EXECUTIVE OPERATION MANAGEMENT SERVICES CONTROLLERS ---

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    routes = conn.execute("SELECT * FROM routes").fetchall()
    saccos = conn.execute("SELECT * FROM saccos").fetchall()
    
    buses = conn.execute("""
        SELECT b.*, r.route_name, s.sacco_name 
        FROM buses b 
        LEFT JOIN routes r ON b.route_id = r.route_id
        LEFT JOIN saccos s ON b.sacco_id = s.sacco_id
    """).fetchall()
    
    subs = conn.execute("""
        SELECT s.*, u.name as passenger_name, r.route_name FROM subscriptions s
        JOIN users u ON s.passenger_id = u.user_id
        JOIN routes r ON s.route_id = r.route_id
    """).fetchall()
    
    payments = conn.execute("""
        SELECT p.*, u.name as passenger_name FROM payments p 
        JOIN users u ON p.passenger_id = u.user_id
    """).fetchall()
    conn.close()
    
    return render_template('admin.html', routes=routes, saccos=saccos, buses=buses, subs=subs, payments=payments)

@app.route('/admin/route/add', methods=['POST'])
def add_route():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    name = request.form['route_name']
    distance = request.form['distance']
    fare = request.form['monthly_fare']
    
    conn = get_db_connection()
    conn.execute("INSERT INTO routes (route_name, distance, monthly_fare) VALUES (?, ?, ?)", (name, distance, fare))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/bus/add', methods=['POST'])
def add_bus():
    if session.get('role') != 'admin': 
        return redirect(url_for('login'))
        
    plate = request.form['plate_number']
    route_id = request.form['route_id']
    capacity = request.form['capacity']
    sacco_id = request.form['sacco_id']
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO buses (plate_number, route_id, capacity, sacco_id) VALUES (?, ?, ?, ?)", 
            (plate, route_id, capacity, sacco_id)
        )
        conn.commit()
        flash("Bus enrolled successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Error: That bus plate number is already registered in the system.", "error")
    finally:
        conn.close() 
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/saccos', methods=['GET', 'POST'])
def manage_saccos():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        sacco_name = request.form.get('sacco_name').strip()
        contact = request.form.get('contact_number').strip()
        
        if sacco_name:
            try:
                conn.execute("INSERT INTO saccos (sacco_name, contact_number) VALUES (?, ?)", (sacco_name, contact))
                conn.commit()
                flash(f"Sacco '{sacco_name}' added successfully!", "success")
            except sqlite3.IntegrityError:
                flash("That Sacco name already exists!", "danger")
                
    saccos = conn.execute("SELECT * FROM saccos").fetchall()
    conn.close()
    return render_template('admin_saccos.html', saccos=saccos)

@app.route('/admin/subscription/<int:sub_id>/<string:action>')
def handle_sub(sub_id, action):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    new_status = 'approved' if action == 'approve' else 'rejected'
    
    conn = get_db_connection()
    if new_status == 'approved':
        sub = conn.execute("SELECT route_id, passenger_id FROM subscriptions WHERE subscription_id=?", (sub_id,)).fetchone()
        if sub:
            total_cap = conn.execute("SELECT SUM(capacity) FROM buses WHERE route_id=?", (sub['route_id'],)).fetchone()[0] or 0
            active_count = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE route_id=? AND status='approved'", (sub['route_id'],)).fetchone()[0]
            
            if active_count >= total_cap:
                flash("Approval blocked: Route capacity limit hit.", "error")
                conn.close()
                return redirect(url_for('admin_dashboard'))
                
            conn.execute("UPDATE subscriptions SET status='approved' WHERE subscription_id=?", (sub_id,))
            fare = conn.execute("SELECT monthly_fare FROM routes WHERE route_id=?", (sub['route_id'],)).fetchone()['monthly_fare']
            current_month = datetime.now().strftime("%B %Y")
            conn.execute(
                "INSERT INTO payments (passenger_id, subscription_id, amount, month, status) VALUES (?, ?, ?, ?, 'unpaid')",
                (sub['passenger_id'], sub_id, fare, current_month)
            )
    else:
        conn.execute("UPDATE subscriptions SET status='rejected' WHERE subscription_id=?", (sub_id,))
        
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# --- CONSUMER COMMUTER SUBSCRIBERS VIEWS SERVICES CONTROLLERS ---

@app.route('/passenger')
def passenger_dashboard():
    if session.get('role') != 'passenger':
        return redirect(url_for('login'))
        
    p_id = session['user_id']
    conn = get_db_connection()
    routes = conn.execute("SELECT * FROM routes").fetchall()
    
    my_subs = conn.execute("""
        SELECT s.*, r.route_name, r.monthly_fare 
        FROM subscriptions s 
        JOIN routes r ON s.route_id = r.route_id 
        WHERE s.passenger_id=?
    """, (p_id,)).fetchall()
    
    my_payments = conn.execute("SELECT * FROM payments WHERE passenger_id=?", (p_id,)).fetchall()
    conn.close()
    
    return render_template('passenger.html', routes=routes, my_subs=my_subs, my_payments=my_payments)

@app.route('/passenger/subscribe', methods=['POST'])
def request_sub():
    if session.get('role') != 'passenger': return redirect(url_for('login'))
    route_id = request.form['route_id']
    p_id = session['user_id']
    
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM subscriptions WHERE passenger_id=? AND route_id=? AND status IN ('pending', 'approved')", 
        (p_id, route_id)
    ).fetchone()
    
    if existing:
        flash("You already have an active or pending entry tracking this route.", "error")
    else:
        conn.execute("INSERT INTO subscriptions (passenger_id, route_id) VALUES (?, ?)", (p_id, route_id))
        conn.commit()
    conn.close()
    return redirect(url_for('passenger_dashboard'))

@app.route('/passenger/pay/<int:payment_id>')
def pay_invoice(payment_id):
    if session.get('role') != 'passenger': return redirect(url_for('login'))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    conn.execute("UPDATE payments SET status='paid', payment_date=? WHERE payment_id=?", (timestamp, payment_id))
    conn.commit()
    conn.close()
    return redirect(url_for('passenger_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)