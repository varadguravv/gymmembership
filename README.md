# 🏋️ Gym Membership Management System

A complete, professional web application for managing gym memberships, built with **Python Flask** and **MySQL**.

## Features

- **Admin Login** — Secure login with hashed passwords (werkzeug)
- **Dashboard** — Stats, revenue, expiring memberships, recent payments
- **Members** — Add, view, edit, delete with search & filter
- **Trainers** — Manage trainers and their assigned members
- **Plans** — Create and manage subscription plans
- **Memberships** — Track active/expired memberships, auto-calculate end dates
- **Payments** — Monthly filter, mark as paid, overdue highlights
- **Notices** — Post and manage gym announcements
- **Settings** — Change password, update gym name

## Tech Stack

- **Backend:** Python 3.x, Flask, Flask-Login
- **Database:** MySQL via PyMySQL
- **Frontend:** Bootstrap 5, Bootstrap Icons
- **Auth:** Werkzeug password hashing

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
Copy `.env.example` to `.env` and fill in your MySQL credentials:
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=gym_management
SECRET_KEY=your-secret-key
```

### 3. Create the database
```bash
mysql -u root -p -e "CREATE DATABASE gym_management;"
```

### 4. Initialize tables and seed data
```bash
flask init-db
```

### 5. Run the application
```bash
python app.py
```

Visit: **http://localhost:5000**

## Default Login

| Field    | Value           |
|----------|-----------------|
| Email    | admin@gym.com   |
| Password | admin123        |

## File Structure

```
├── app.py              # Main Flask application
├── schema.sql          # Database schema
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not committed)
├── .env.example        # Environment template
├── templates/          # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── members.html
│   ├── member_detail.html
│   ├── add_member.html
│   ├── trainers.html
│   ├── trainer_detail.html
│   ├── add_trainer.html
│   ├── plans.html
│   ├── add_plan.html
│   ├── memberships.html
│   ├── add_membership.html
│   ├── payments.html
│   ├── notices.html
│   └── settings.html
└── static/
    ├── css/custom.css
    └── js/main.js
```
