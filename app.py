from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
# Application object for WSGI servers (AWS Elastic Beanstalk expects `application` by default)
application = app

# Secret key should come from environment in production - EB environment variables can be set
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')  # change via EB config

DATABASE = 'database.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        db.commit()
        # Insert sample users if not exist
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            # Admin user
            hashed_pw = generate_password_hash('admin123')
            db.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                       ('Admin User', 'admin@example.com', hashed_pw, 'admin'))
            # Employee users
            hashed_pw_emp = generate_password_hash('emp123')
            db.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                       ('John Doe', 'john@example.com', hashed_pw_emp, 'employee'))
            db.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                       ('Jane Smith', 'jane@example.com', hashed_pw_emp, 'employee'))
        db.commit()

@app.route('/')
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    email = request.form['email']
    password = request.form['password']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['name'] = user['name']
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid email or password')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    # Get attendance history for the user
    attendance = db.execute("SELECT date, status, timestamp FROM attendance WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()
    return render_template('dashboard.html', attendance=attendance)

@app.route('/mark/<status>')
def mark_attendance(status):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if status not in ['Present', 'Absent']:
        flash('Invalid status')
        return redirect(url_for('dashboard'))
    user_id = session['user_id']
    today = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    # Check if already marked today
    existing = db.execute("SELECT id FROM attendance WHERE user_id = ? AND date = ?", (user_id, today)).fetchone()
    if existing:
        flash('Attendance already marked for today')
        return redirect(url_for('dashboard'))
    # Insert new record
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("INSERT INTO attendance (user_id, date, status, timestamp) VALUES (?, ?, ?, ?)",
               (user_id, today, status, timestamp))
    db.commit()
    flash(f'Attendance marked as {status}')
    return redirect(url_for('dashboard'))

@app.route('/admin')
def admin():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    users = db.execute("SELECT id, name, email, role FROM users").fetchall()
    date_filter = request.args.get('date', '')
    if date_filter:
        attendance = db.execute("SELECT a.date, a.status, a.timestamp, u.name FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.date = ? ORDER BY a.timestamp DESC", (date_filter,)).fetchall()
    else:
        attendance = db.execute("SELECT a.date, a.status, a.timestamp, u.name FROM attendance a JOIN users u ON a.user_id = u.id ORDER BY a.date DESC, a.timestamp DESC").fetchall()
    return render_template('admin.html', users=users, attendance=attendance, date_filter=date_filter)

# initialize the database whenever the module is imported by the WSGI server
init_db()

if __name__ == '__main__':
    # local dev entrypoint
    app.run(debug=True)