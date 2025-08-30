from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from passlib.hash import bcrypt
import pymysql
from datetime import datetime
from config import Config
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "complaint_mgmt", "templates"),
    static_folder=os.path.join(BASE_DIR, "complaint_mgmt", "static")
)
app.config.from_object(Config)

# ---- Database helper ----

def get_conn():
    return pymysql.connect(
        host=app.config['DB_HOST'],
        port=app.config['DB_PORT'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        database=app.config['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

# ---- Auth utilities ----

def login_required(role=None):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# ---- Routes ----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or not password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        pwd_hash = bcrypt.hash(password)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,%s)",
                                (name, email, pwd_hash, 'user'))
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except pymysql.err.IntegrityError:
            flash('Email already registered', 'warning')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
        if user and bcrypt.verify(password, user['password_hash']):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash('Welcome, ' + user['name'], 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required()
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# ---- User area ----
@app.route('/dashboard')
@login_required()
def dashboard():
    user_id = session['user_id']
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    SUM(CASE WHEN status='Submitted' THEN 1 ELSE 0 END) AS submitted,
                    SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END) AS in_progress,
                    SUM(CASE WHEN status IN ('Resolved','Closed') THEN 1 ELSE 0 END) AS resolved
                FROM complaints WHERE user_id=%s
            """, (user_id,))
            counts = cur.fetchone() or {'submitted':0,'in_progress':0,'resolved':0}
            cur.execute("SELECT * FROM complaints WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (user_id,))
            latest = cur.fetchall()
    return render_template('dashboard.html', counts=counts, latest=latest)

@app.route('/complaints/new', methods=['GET','POST'])
@login_required()
def submit_complaint():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        category = request.form.get('category','General').strip()
        description = request.form.get('description','').strip()
        priority = request.form.get('priority','Medium')
        if not title or not description:
            flash('Title and description are required', 'danger')
            return render_template('submit_complaint.html')
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO complaints(user_id,title,category,description,priority) VALUES(%s,%s,%s,%s,%s)",
                    (session['user_id'], title, category, description, priority)
                )
        flash('Complaint submitted successfully', 'success')
        return redirect(url_for('my_complaints'))
    return render_template('submit_complaint.html')

@app.route('/complaints')
@login_required()
def my_complaints():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM complaints WHERE user_id=%s ORDER BY created_at DESC", (session['user_id'],))
            rows = cur.fetchall()
    return render_template('my_complaints.html', complaints=rows)

@app.route('/complaints/<int:complaint_id>')
@login_required()
def complaint_detail(complaint_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM complaints WHERE id=%s AND user_id=%s", (complaint_id, session['user_id']))
            comp = cur.fetchone()
            if not comp:
                abort(404)
            cur.execute("SELECT h.*, u.name as actor_name FROM complaint_history h JOIN users u ON u.id=h.action_by WHERE complaint_id=%s ORDER BY action_at DESC", (complaint_id,))
            history = cur.fetchall()
            cur.execute("SELECT * FROM feedback WHERE complaint_id=%s AND user_id=%s", (complaint_id, session['user_id']))
            fb = cur.fetchone()
    return render_template('complaint_detail.html', comp=comp, history=history, fb=fb)
@app.route('/complaints/<int:complaint_id>/feedback', methods=['POST'])
@login_required()
def leave_feedback(complaint_id):
    rating = int(request.form.get('rating', '0'))
    comments = request.form.get('comments','').strip()
    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5', 'warning')
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Only allow feedback when Resolved or Closed
            cur.execute("SELECT status FROM complaints WHERE id=%s AND user_id=%s", (complaint_id, session['user_id']))
            row = cur.fetchone()
            if not row:
                abort(404)
            if row['status'] not in ('Resolved','Closed'):
                flash('You can leave feedback only after resolution', 'warning')
                return redirect(url_for('complaint_detail', complaint_id=complaint_id))
            cur.execute("SELECT id FROM feedback WHERE complaint_id=%s AND user_id=%s", (complaint_id, session['user_id']))
            existing = cur.fetchone()
            if existing:
                cur.execute("UPDATE feedback SET rating=%s, comments=%s WHERE id=%s", (rating, comments, existing['id']))
            else:
                cur.execute("INSERT INTO feedback(complaint_id,user_id,rating,comments) VALUES(%s,%s,%s,%s)", (complaint_id, session['user_id'], rating, comments))
    flash('Thanks for your feedback!', 'success')
    return redirect(url_for('complaint_detail', complaint_id=complaint_id))

# ---- Admin area ----
@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    status = request.args.get('status')
    query = "SELECT c.*, u.name as user_name, u.email FROM complaints c JOIN users u ON u.id=c.user_id"
    params = []
    if status:
        query += " WHERE c.status=%s"
        params.append(status)
    query += " ORDER BY c.created_at DESC"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.execute("""
                SELECT
                SUM(CASE WHEN status='Submitted' THEN 1 ELSE 0 END) submitted,
                SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END) in_progress,
                SUM(CASE WHEN status='Resolved' THEN 1 ELSE 0 END) resolved,
                SUM(CASE WHEN status='Closed' THEN 1 ELSE 0 END) closed
                FROM complaints
            """)
            counts = cur.fetchone() or {}
    return render_template('admin_dashboard.html', complaints=rows, counts=counts, filter_status=status)

@app.route('/admin/complaints/<int:complaint_id>', methods=['GET','POST'])
@login_required(role='admin')
def admin_complaint_detail(complaint_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT c.*, u.name as user_name, u.email FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.id=%s", (complaint_id,))
            comp = cur.fetchone()
            if not comp:
                abort(404)
            if request.method == 'POST':
                new_status = request.form.get('status', comp['status'])
                note = request.form.get('note','').strip()
                old_status = comp['status']
                cur.execute("UPDATE complaints SET status=%s WHERE id=%s", (new_status, complaint_id))
                cur.execute("INSERT INTO complaint_history(complaint_id, action_by, old_status, new_status, note) VALUES(%s,%s,%s,%s,%s)",
                            (complaint_id, session['user_id'], old_status, new_status, note))
                flash('Status updated', 'success')
                return redirect(url_for('admin_complaint_detail', complaint_id=complaint_id))
            cur.execute("SELECT h.*, u.name as actor_name FROM complaint_history h JOIN users u ON u.id=h.action_by WHERE complaint_id=%s ORDER BY action_at DESC", (complaint_id,))
            history = cur.fetchall()
    return render_template('admin_complaint_detail.html', comp=comp, history=history)

# ---- Error handlers ----
@app.errorhandler(403)
def forbidden(e):
    return render_template('base.html', content="<div class='container'><h2>403 – Forbidden</h2><p>You do not have access to this page.</p></div>"), 403

@app.errorhandler(404)
def notfound(e):
    return render_template('base.html', content="<div class='container'><h2>404 – Not Found</h2><p>Item not found.</p></div>"), 404

# ---- Run ----
if __name__ == '__main__':
    app.run(debug=True)
            