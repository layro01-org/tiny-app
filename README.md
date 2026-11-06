# Tiny Python Web App - Secure Authentication

A minimal Flask web application with role-based access control, user authentication, event logging, and HTTPS support.

## Features

- **User Registration & Login** — Secure password hashing (PBKDF2-SHA256)
- **Role-Based Access Control** — Admin and User roles
- **Admin Panel** — Manage users, view statistics, inspect event logs
- **Event Logging** — Audit trail to `logs/events.log`
- **Security Headers** — XSS, clickjacking, MIME-type protection
- **HTTPS Support** — Self-signed certificate for development

## Quick Start

### 1. Clone & Setup Virtual Environment

```bash
git clone <your-repo-url>
cd tiny-python-app
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the App

**HTTP (default):**
```bash
python3 app.py
```

**HTTPS (with self-signed cert):**
```bash
USE_HTTPS=true python3 app.py
```

Then open:
- HTTP: `http://127.0.0.1:5000`
- HTTPS: `https://127.0.0.1:5000`

## Usage

1. **Register** — Create your first account (automatically becomes admin)
2. **Login** — Use your credentials
3. **Dashboard** — View your profile
4. **Admin Panel** — Manage users and view logs

## Project Structure

```
.
├── app.py                 # Flask application & routes
├── requirements.txt       # Python dependencies
├── .env                   # Environment configuration
├── cert.pem              # Self-signed SSL certificate
├── key.pem               # SSL private key
├── templates/            # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── admin.html
│   ├── admin_users.html
│   └── admin_logs.html
└── logs/                 # Event log directory
    └── events.log
```

## Configuration

Edit `.env`:
```
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

## Security Notes

- Passwords are hashed with PBKDF2-SHA256
- Cookies use HttpOnly, Secure, and SameOrigin flags
- All admin actions are logged
- First registered user automatically becomes admin

## Database

Uses SQLite with auto-migration on startup. Database file: `instance/users.db`

## License

MIT
