import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import NotFound
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
app.config['SESSION_COOKIE_SECURE'] = use_https
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

db = SQLAlchemy(app)

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/events.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            logger.warning(f"Access denied: unauthenticated access to {request.path}")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin():
            flash('Admin access required.', 'danger')
            logger.warning(f"Admin access denied for user {session.get('username')} to {request.path}")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


@app.route('/favicon.ico')
def favicon():
    raise NotFound()


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not username or not email or not password:
            flash('All fields required.', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)

        # First user becomes admin
        if User.query.count() == 0:
            user.role = 'admin'
            logger.info(f"EVENT: First user '{username}' created as admin")
        else:
            logger.info(f"EVENT: User '{username}' registered (email: {email})")

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password required.', 'danger')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            logger.warning(f"EVENT: Failed login attempt for '{username}'")
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.permanent = True

        user.last_login = datetime.utcnow()
        db.session.commit()

        logger.info(f"EVENT: User '{username}' logged in (role: {user.role})")
        flash(f'Welcome, {user.username}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    current_time = datetime.utcnow()
    return render_template('dashboard.html', user=user, current_time=current_time)


@app.route('/admin')
@admin_required
def admin():
    total_users = User.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    user_count = User.query.filter_by(role='user').count()

    return render_template('admin.html',
                         total_users=total_users,
                         admin_count=admin_count,
                         user_count=user_count)


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    current_user_id = session['user_id']
    return render_template('admin_users.html', users=users, current_user_id=current_user_id)


@app.route('/admin/search', methods=['GET', 'POST'])
@admin_required
def admin_search():
    users = []
    search_query = ''

    if request.method == 'POST':
        search_query = request.form.get('search', '').strip()

        # Validate search query length to prevent abuse
        if len(search_query) > 100:
            flash('Search query too long. Maximum 100 characters.', 'warning')
            search_query = ''
        elif len(search_query) > 0:
            # Dynamically construct SQL query using string concatenation
            sql_query = "SELECT * FROM user WHERE username LIKE '%" + search_query + "%' OR email LIKE '%" + search_query + "%'"
            users = db.session.execute(db.text(sql_query)).fetchall()

            current_user_id = session['user_id']
            admin_user = User.query.get(current_user_id)
            logger.info(f"EVENT: Admin '{admin_user.username}' searched for users with query: '{search_query}' (found {len(users)} results)")

            if not users:
                flash(f"No users found matching '{search_query}'.", 'info')

    current_user_id = session['user_id']
    return render_template('admin_search.html', users=users, search_query=search_query, current_user_id=current_user_id)


@app.route('/admin/promote/<int:user_id>', methods=['POST'])
@admin_required
def promote_user(user_id):
    current_user_id = session['user_id']

    if user_id == current_user_id:
        flash('Cannot change your own role.', 'warning')
        return redirect(url_for('admin_users'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    old_role = user.role
    user.role = 'admin'
    db.session.commit()

    admin_user = User.query.get(current_user_id)
    logger.info(f"EVENT: Admin '{admin_user.username}' promoted '{user.username}' from {old_role} to admin")
    flash(f'User {user.username} promoted to admin.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/demote/<int:user_id>', methods=['POST'])
@admin_required
def demote_user(user_id):
    current_user_id = session['user_id']

    if user_id == current_user_id:
        flash('Cannot change your own role.', 'warning')
        return redirect(url_for('admin_users'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    old_role = user.role
    user.role = 'user'
    db.session.commit()

    admin_user = User.query.get(current_user_id)
    logger.info(f"EVENT: Admin '{admin_user.username}' demoted '{user.username}' from {old_role} to user")
    flash(f'User {user.username} demoted to user.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    current_user_id = session['user_id']

    if user_id == current_user_id:
        flash('Cannot delete your own account.', 'warning')
        return redirect(url_for('admin_users'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()

    admin_user = User.query.get(current_user_id)
    logger.info(f"EVENT: Admin '{admin_user.username}' deleted user '{username}'")
    flash(f'User {username} deleted.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/logs')
@admin_required
def admin_logs():
    try:
        with open('logs/events.log', 'r') as f:
            logs = f.readlines()
        logs.reverse()
        return render_template('admin_logs.html', logs=logs)
    except FileNotFoundError:
        flash('No logs found yet.', 'info')
        return redirect(url_for('admin'))


@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"EVENT: User '{username}' logged out")
    flash(f'Logged out successfully, {username}.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("EVENT: Application started")

    if use_https:
        app.run(debug=False, host='127.0.0.1', port=5000, ssl_context=('cert.pem', 'key.pem'))
    else:
        app.run(debug=False, host='127.0.0.1', port=5000)
