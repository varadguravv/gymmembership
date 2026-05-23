import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gym-secret-key-2024')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# ─── DB Connection ────────────────────────────────────────────────────────────
def get_db():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'gym_management'),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# ─── Admin User Model ─────────────────────────────────────────────────────────
class Admin(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM admins WHERE id = %s", (user_id,))
        row = cur.fetchone()
    db.close()
    if row:
        return Admin(row['id'], row['name'], row['email'])
    return None

# ─── Helper ───────────────────────────────────────────────────────────────────
def get_gym_name():
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE `key`='gym_name'")
            row = cur.fetchone()
        db.close()
        return row['value'] if row else 'FitZone Gym'
    except:
        return 'FitZone Gym'

@app.context_processor
def inject_globals():
    return {'now': datetime.now(), 'gym_name': get_gym_name()}

# ─── Auto-initialize DB on first run ─────────────────────────────────────────
def auto_init_db():
    """Creates tables and seeds default data if they don't exist yet."""
    try:
        db = get_db()
        statements = [
            """CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                phone VARCHAR(20),
                join_date DATE NOT NULL,
                status ENUM('active','expired','inactive') DEFAULT 'active'
            )""",
            """CREATE TABLE IF NOT EXISTS trainers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                specialization VARCHAR(150),
                phone VARCHAR(20),
                email VARCHAR(150) UNIQUE NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS plans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                plan_name VARCHAR(100) NOT NULL,
                duration_months INT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                description TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS memberships (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                plan_id INT NOT NULL,
                trainer_id INT,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                status ENUM('active','expired') DEFAULT 'active',
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
                FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
            )""",
            """CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                membership_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date DATE NOT NULL,
                status ENUM('paid','pending') DEFAULT 'pending',
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS notices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                posted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_id INT,
                FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL
            )""",
            """CREATE TABLE IF NOT EXISTS settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `key` VARCHAR(100) UNIQUE NOT NULL,
                value TEXT
            )""",
        ]
        with db.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
            # Seed default admin
            cur.execute("SELECT id FROM admins WHERE email='admin@gym.com'")
            if not cur.fetchone():
                h = generate_password_hash('admin123')
                cur.execute(
                    "INSERT INTO admins (name,email,password_hash) VALUES ('Admin','admin@gym.com',%s)", (h,)
                )
            # Seed gym name
            cur.execute(
                "INSERT INTO settings (`key`,value) VALUES ('gym_name','FitZone Gym') "
                "ON DUPLICATE KEY UPDATE `key`=`key`"
            )
            # Seed sample plans
            cur.execute("SELECT id FROM plans LIMIT 1")
            if not cur.fetchone():
                cur.executemany(
                    "INSERT INTO plans (plan_name,duration_months,price,description) VALUES (%s,%s,%s,%s)",
                    [
                        ('Basic Monthly',       1,  999.00, 'Access to gym floor and basic equipment'),
                        ('Standard Quarterly',  3, 2499.00, 'Full gym access with locker facility'),
                        ('Premium Half-Yearly', 6, 4499.00, 'Full access + 1 personal training session/month'),
                        ('Elite Annual',       12, 7999.00, 'Unlimited access + personal trainer + diet plan'),
                    ]
                )
        db.close()
    except Exception as e:
        print(f'[auto_init_db] {e}')

auto_init_db()

# ─── Auth Routes ──────────────────────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
            admin = cur.fetchone()
        db.close()
        if admin and check_password_hash(admin['password_hash'], password):
            user = Admin(admin['id'], admin['name'], admin['email'])
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM members")
        total_members = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM members WHERE status='active'")
        active_members = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM members WHERE status='expired'")
        expired_members = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM payments WHERE status='pending'")
        pending_payments = cur.fetchone()['cnt']
        cur.execute("""SELECT COALESCE(SUM(amount),0) as rev FROM payments
                       WHERE status='paid' AND MONTH(payment_date)=MONTH(CURDATE())
                       AND YEAR(payment_date)=YEAR(CURDATE())""")
        monthly_revenue = cur.fetchone()['rev']
        today = date.today()
        soon = today + timedelta(days=7)
        cur.execute("""SELECT m.name, ms.end_date, p.plan_name
                       FROM memberships ms
                       JOIN members m ON ms.member_id=m.id
                       JOIN plans p ON ms.plan_id=p.id
                       WHERE ms.status='active' AND ms.end_date BETWEEN %s AND %s
                       ORDER BY ms.end_date""", (today, soon))
        expiring_soon = cur.fetchall()
        cur.execute("""SELECT m.name as member_name, p.plan_name, py.amount, py.payment_date, py.status
                       FROM payments py
                       JOIN members m ON py.member_id=m.id
                       JOIN memberships ms ON py.membership_id=ms.id
                       JOIN plans p ON ms.plan_id=p.id
                       ORDER BY py.payment_date DESC LIMIT 8""")
        recent_payments = cur.fetchall()
        cur.execute("SELECT * FROM notices ORDER BY posted_date DESC LIMIT 3")
        notices = cur.fetchall()
    db.close()
    gym_name = get_gym_name()
    return render_template('dashboard.html',
        total_members=total_members, active_members=active_members,
        expired_members=expired_members, pending_payments=pending_payments,
        monthly_revenue=monthly_revenue, expiring_soon=expiring_soon,
        recent_payments=recent_payments, notices=notices, gym_name=gym_name)

# ─── Members ──────────────────────────────────────────────────────────────────
@app.route('/members')
@login_required
def members():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')
    db = get_db()
    with db.cursor() as cur:
        query = """SELECT m.*, ms.end_date, p.plan_name
                   FROM members m
                   LEFT JOIN memberships ms ON ms.member_id=m.id
                     AND ms.id=(SELECT id FROM memberships WHERE member_id=m.id ORDER BY end_date DESC LIMIT 1)
                   LEFT JOIN plans p ON ms.plan_id=p.id
                   WHERE 1=1"""
        params = []
        if search:
            query += " AND (m.name LIKE %s OR m.phone LIKE %s)"
            params += [f'%{search}%', f'%{search}%']
        if status_filter != 'all':
            query += " AND m.status=%s"
            params.append(status_filter)
        query += " ORDER BY m.join_date DESC"
        cur.execute(query, params)
        members_list = cur.fetchall()
    db.close()
    return render_template('members.html', members=members_list,
                           search=search, status_filter=status_filter)

@app.route('/members/add', methods=['GET', 'POST'])
@login_required
def add_member():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        join_date = request.form['join_date']
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("INSERT INTO members (name,email,phone,join_date,status) VALUES (%s,%s,%s,%s,'active')",
                            (name, email, phone, join_date))
            flash('Member added successfully!', 'success')
            return redirect(url_for('members'))
        except pymysql.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            db.close()
    return render_template('add_member.html')

@app.route('/members/<int:member_id>')
@login_required
def member_detail(member_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM members WHERE id=%s", (member_id,))
        member = cur.fetchone()
        if not member:
            flash('Member not found.', 'danger')
            return redirect(url_for('members'))
        cur.execute("""SELECT ms.*, p.plan_name, p.duration_months, p.price,
                              t.name as trainer_name, t.specialization
                       FROM memberships ms
                       JOIN plans p ON ms.plan_id=p.id
                       LEFT JOIN trainers t ON ms.trainer_id=t.id
                       WHERE ms.member_id=%s ORDER BY ms.start_date DESC""", (member_id,))
        memberships = cur.fetchall()
        cur.execute("""SELECT py.*, p.plan_name FROM payments py
                       JOIN memberships ms ON py.membership_id=ms.id
                       JOIN plans p ON ms.plan_id=p.id
                       WHERE py.member_id=%s ORDER BY py.payment_date DESC""", (member_id,))
        payments = cur.fetchall()
    db.close()
    current_membership = memberships[0] if memberships else None
    return render_template('member_detail.html', member=member,
                           memberships=memberships, payments=payments,
                           current_membership=current_membership)

@app.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(member_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM members WHERE id=%s", (member_id,))
        member = cur.fetchone()
    if not member:
        db.close()
        flash('Member not found.', 'danger')
        return redirect(url_for('members'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        status = request.form['status']
        try:
            with db.cursor() as cur:
                cur.execute("UPDATE members SET name=%s,email=%s,phone=%s,status=%s WHERE id=%s",
                            (name, email, phone, status, member_id))
            flash('Member updated successfully!', 'success')
            return redirect(url_for('member_detail', member_id=member_id))
        except pymysql.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            db.close()
    db.close()
    return render_template('add_member.html', member=member, edit=True)

@app.route('/members/<int:member_id>/delete', methods=['POST'])
@login_required
def delete_member(member_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM members WHERE id=%s", (member_id,))
    db.close()
    flash('Member deleted successfully.', 'success')
    return redirect(url_for('members'))

# ─── Trainers ─────────────────────────────────────────────────────────────────
@app.route('/trainers')
@login_required
def trainers():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT t.*,
                       COUNT(DISTINCT ms.member_id) as assigned_count
                       FROM trainers t
                       LEFT JOIN memberships ms ON ms.trainer_id=t.id AND ms.status='active'
                       GROUP BY t.id ORDER BY t.name""")
        trainers_list = cur.fetchall()
    db.close()
    return render_template('trainers.html', trainers=trainers_list)

@app.route('/trainers/add', methods=['GET', 'POST'])
@login_required
def add_trainer():
    if request.method == 'POST':
        name = request.form['name'].strip()
        specialization = request.form['specialization'].strip()
        phone = request.form['phone'].strip()
        email = request.form['email'].strip()
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("INSERT INTO trainers (name,specialization,phone,email) VALUES (%s,%s,%s,%s)",
                            (name, specialization, phone, email))
            flash('Trainer added successfully!', 'success')
            return redirect(url_for('trainers'))
        except pymysql.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            db.close()
    return render_template('add_trainer.html')

@app.route('/trainers/<int:trainer_id>')
@login_required
def trainer_detail(trainer_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM trainers WHERE id=%s", (trainer_id,))
        trainer = cur.fetchone()
        if not trainer:
            flash('Trainer not found.', 'danger')
            return redirect(url_for('trainers'))
        cur.execute("""SELECT m.*, ms.start_date, ms.end_date, ms.status as ms_status, p.plan_name
                       FROM memberships ms
                       JOIN members m ON ms.member_id=m.id
                       JOIN plans p ON ms.plan_id=p.id
                       WHERE ms.trainer_id=%s ORDER BY ms.start_date DESC""", (trainer_id,))
        assigned_members = cur.fetchall()
    db.close()
    return render_template('trainer_detail.html', trainer=trainer, assigned_members=assigned_members)

@app.route('/trainers/<int:trainer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trainer(trainer_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM trainers WHERE id=%s", (trainer_id,))
        trainer = cur.fetchone()
    if not trainer:
        db.close()
        flash('Trainer not found.', 'danger')
        return redirect(url_for('trainers'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        specialization = request.form['specialization'].strip()
        phone = request.form['phone'].strip()
        email = request.form['email'].strip()
        try:
            with db.cursor() as cur:
                cur.execute("UPDATE trainers SET name=%s,specialization=%s,phone=%s,email=%s WHERE id=%s",
                            (name, specialization, phone, email, trainer_id))
            flash('Trainer updated successfully!', 'success')
            return redirect(url_for('trainers'))
        except pymysql.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            db.close()
    db.close()
    return render_template('add_trainer.html', trainer=trainer, edit=True)

@app.route('/trainers/<int:trainer_id>/delete', methods=['POST'])
@login_required
def delete_trainer(trainer_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM trainers WHERE id=%s", (trainer_id,))
    db.close()
    flash('Trainer deleted successfully.', 'success')
    return redirect(url_for('trainers'))

# ─── Plans ────────────────────────────────────────────────────────────────────
@app.route('/plans')
@login_required
def plans():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT p.*, COUNT(ms.id) as active_subscriptions
                       FROM plans p
                       LEFT JOIN memberships ms ON ms.plan_id=p.id AND ms.status='active'
                       GROUP BY p.id ORDER BY p.price""")
        plans_list = cur.fetchall()
    db.close()
    return render_template('plans.html', plans=plans_list)

@app.route('/plans/add', methods=['GET', 'POST'])
@login_required
def add_plan():
    if request.method == 'POST':
        plan_name = request.form['plan_name'].strip()
        duration_months = int(request.form['duration_months'])
        price = float(request.form['price'])
        description = request.form['description'].strip()
        db = get_db()
        with db.cursor() as cur:
            cur.execute("INSERT INTO plans (plan_name,duration_months,price,description) VALUES (%s,%s,%s,%s)",
                        (plan_name, duration_months, price, description))
        db.close()
        flash('Plan added successfully!', 'success')
        return redirect(url_for('plans'))
    return render_template('add_plan.html')

@app.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_plan(plan_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM plans WHERE id=%s", (plan_id,))
        plan = cur.fetchone()
    if not plan:
        db.close()
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans'))
    if request.method == 'POST':
        plan_name = request.form['plan_name'].strip()
        duration_months = int(request.form['duration_months'])
        price = float(request.form['price'])
        description = request.form['description'].strip()
        with db.cursor() as cur:
            cur.execute("UPDATE plans SET plan_name=%s,duration_months=%s,price=%s,description=%s WHERE id=%s",
                        (plan_name, duration_months, price, description, plan_id))
        db.close()
        flash('Plan updated successfully!', 'success')
        return redirect(url_for('plans'))
    db.close()
    return render_template('add_plan.html', plan=plan, edit=True)

@app.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete_plan(plan_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM plans WHERE id=%s", (plan_id,))
    db.close()
    flash('Plan deleted successfully.', 'success')
    return redirect(url_for('plans'))

# ─── Memberships ──────────────────────────────────────────────────────────────
@app.route('/memberships')
@login_required
def memberships():
    status_filter = request.args.get('status', 'all')
    db = get_db()
    with db.cursor() as cur:
        query = """SELECT ms.*, m.name as member_name, p.plan_name,
                          t.name as trainer_name
                   FROM memberships ms
                   JOIN members m ON ms.member_id=m.id
                   JOIN plans p ON ms.plan_id=p.id
                   LEFT JOIN trainers t ON ms.trainer_id=t.id
                   WHERE 1=1"""
        params = []
        if status_filter != 'all':
            query += " AND ms.status=%s"
            params.append(status_filter)
        query += " ORDER BY ms.start_date DESC"
        cur.execute(query, params)
        memberships_list = cur.fetchall()
    db.close()
    return render_template('memberships.html', memberships=memberships_list, status_filter=status_filter)

@app.route('/memberships/add', methods=['GET', 'POST'])
@login_required
def add_membership():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM members ORDER BY name")
        members_list = cur.fetchall()
        cur.execute("SELECT * FROM plans ORDER BY price")
        plans_list = cur.fetchall()
        cur.execute("SELECT * FROM trainers ORDER BY name")
        trainers_list = cur.fetchall()
    if request.method == 'POST':
        member_id = int(request.form['member_id'])
        plan_id = int(request.form['plan_id'])
        trainer_id = request.form.get('trainer_id') or None
        start_date_str = request.form['start_date']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        db2 = get_db()
        with db2.cursor() as cur:
            cur.execute("SELECT duration_months, price FROM plans WHERE id=%s", (plan_id,))
            plan = cur.fetchone()
        end_date = start_date + relativedelta(months=plan['duration_months'])
        with db2.cursor() as cur:
            cur.execute("""INSERT INTO memberships (member_id,plan_id,trainer_id,start_date,end_date,status)
                           VALUES (%s,%s,%s,%s,%s,'active')""",
                        (member_id, plan_id, trainer_id, start_date, end_date))
            ms_id = cur.lastrowid
            cur.execute("""INSERT INTO payments (member_id,membership_id,amount,payment_date,status)
                           VALUES (%s,%s,%s,%s,'pending')""",
                        (member_id, ms_id, plan['price'], start_date))
            cur.execute("UPDATE members SET status='active' WHERE id=%s", (member_id,))
        db2.close()
        flash('Membership added successfully!', 'success')
        return redirect(url_for('memberships'))
    return render_template('add_membership.html', members=members_list,
                           plans=plans_list, trainers=trainers_list)

@app.route('/memberships/<int:ms_id>/renew', methods=['POST'])
@login_required
def renew_membership(ms_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT ms.*, p.duration_months, p.price
                       FROM memberships ms JOIN plans p ON ms.plan_id=p.id
                       WHERE ms.id=%s""", (ms_id,))
        ms = cur.fetchone()
    if ms:
        new_start = date.today()
        new_end = new_start + relativedelta(months=ms['duration_months'])
        with db.cursor() as cur:
            cur.execute("""INSERT INTO memberships (member_id,plan_id,trainer_id,start_date,end_date,status)
                           VALUES (%s,%s,%s,%s,%s,'active')""",
                        (ms['member_id'], ms['plan_id'], ms['trainer_id'], new_start, new_end))
            new_ms_id = cur.lastrowid
            cur.execute("""INSERT INTO payments (member_id,membership_id,amount,payment_date,status)
                           VALUES (%s,%s,%s,%s,'pending')""",
                        (ms['member_id'], new_ms_id, ms['price'], new_start))
            cur.execute("UPDATE memberships SET status='expired' WHERE id=%s", (ms_id,))
            cur.execute("UPDATE members SET status='active' WHERE id=%s", (ms['member_id'],))
        flash('Membership renewed successfully!', 'success')
    db.close()
    return redirect(url_for('memberships'))

# ─── Payments ─────────────────────────────────────────────────────────────────
@app.route('/payments')
@login_required
def payments():
    month_filter = request.args.get('month', '')
    db = get_db()
    with db.cursor() as cur:
        query = """SELECT py.*, m.name as member_name, p.plan_name
                   FROM payments py
                   JOIN members m ON py.member_id=m.id
                   JOIN memberships ms ON py.membership_id=ms.id
                   JOIN plans p ON ms.plan_id=p.id
                   WHERE 1=1"""
        params = []
        if month_filter:
            query += " AND DATE_FORMAT(py.payment_date,'%%Y-%%m')=%s"
            params.append(month_filter)
        query += " ORDER BY py.payment_date DESC"
        cur.execute(query, params)
        payments_list = cur.fetchall()
        if month_filter:
            cur.execute("""SELECT COALESCE(SUM(amount),0) as total FROM payments
                           WHERE status='paid' AND DATE_FORMAT(payment_date,'%%Y-%%m')=%s""", (month_filter,))
        else:
            cur.execute("""SELECT COALESCE(SUM(amount),0) as total FROM payments
                           WHERE status='paid' AND MONTH(payment_date)=MONTH(CURDATE())
                           AND YEAR(payment_date)=YEAR(CURDATE())""")
        monthly_total = cur.fetchone()['total']
    db.close()
    return render_template('payments.html', payments=payments_list,
                           monthly_total=monthly_total, month_filter=month_filter)

@app.route('/payments/<int:payment_id>/mark_paid', methods=['POST'])
@login_required
def mark_paid(payment_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("UPDATE payments SET status='paid', payment_date=CURDATE() WHERE id=%s", (payment_id,))
    db.close()
    flash('Payment marked as paid!', 'success')
    return redirect(url_for('payments'))

# ─── Notices ──────────────────────────────────────────────────────────────────
@app.route('/notices')
@login_required
def notices():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT n.*, a.name as admin_name FROM notices n
                       LEFT JOIN admins a ON n.admin_id=a.id
                       ORDER BY n.posted_date DESC""")
        notices_list = cur.fetchall()
    db.close()
    return render_template('notices.html', notices=notices_list)

@app.route('/notices/add', methods=['POST'])
@login_required
def add_notice():
    title = request.form['title'].strip()
    message = request.form['message'].strip()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("INSERT INTO notices (title,message,admin_id) VALUES (%s,%s,%s)",
                    (title, message, current_user.id))
    db.close()
    flash('Notice posted successfully!', 'success')
    return redirect(url_for('notices'))

@app.route('/notices/<int:notice_id>/delete', methods=['POST'])
@login_required
def delete_notice(notice_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM notices WHERE id=%s", (notice_id,))
    db.close()
    flash('Notice deleted.', 'success')
    return redirect(url_for('notices'))

# ─── Settings ─────────────────────────────────────────────────────────────────
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE `key`='gym_name'")
        row = cur.fetchone()
        gym_name = row['value'] if row else 'FitZone Gym'
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pw = request.form['current_password']
            new_pw = request.form['new_password']
            confirm_pw = request.form['confirm_password']
            with db.cursor() as cur:
                cur.execute("SELECT password_hash FROM admins WHERE id=%s", (current_user.id,))
                admin = cur.fetchone()
            if not check_password_hash(admin['password_hash'], current_pw):
                flash('Current password is incorrect.', 'danger')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
            elif len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'danger')
            else:
                new_hash = generate_password_hash(new_pw)
                with db.cursor() as cur:
                    cur.execute("UPDATE admins SET password_hash=%s WHERE id=%s", (new_hash, current_user.id))
                flash('Password changed successfully!', 'success')
        elif action == 'update_gym':
            new_gym_name = request.form['gym_name'].strip()
            with db.cursor() as cur:
                cur.execute("INSERT INTO settings (`key`,value) VALUES ('gym_name',%s) ON DUPLICATE KEY UPDATE value=%s",
                            (new_gym_name, new_gym_name))
            flash('Gym name updated!', 'success')
        db.close()
        return redirect(url_for('settings'))
    db.close()
    return render_template('settings.html', gym_name=gym_name)

# ─── API: Get plan details (for JS auto-fill) ─────────────────────────────────
@app.route('/api/plan/<int:plan_id>')
@login_required
def api_plan(plan_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM plans WHERE id=%s", (plan_id,))
        plan = cur.fetchone()
    db.close()
    if plan:
        return jsonify({'duration_months': plan['duration_months'], 'price': float(plan['price'])})
    return jsonify({}), 404

# ─── Auto-update expired memberships ─────────────────────────────────────────
@app.before_request
def update_expired():
    if request.endpoint in ('static', 'login'):
        return
    try:
        db = get_db()
        with db.cursor() as cur:
            # Expire memberships whose end_date has passed
            cur.execute("UPDATE memberships SET status='expired' WHERE end_date < CURDATE() AND status='active'")
            # Only expire members who HAD a membership that is now all expired
            # (never touch members who have no membership at all - they are new)
            cur.execute("""UPDATE members m SET m.status='expired'
                           WHERE m.status='active'
                           AND EXISTS (
                               SELECT 1 FROM memberships WHERE member_id=m.id
                           )
                           AND m.id NOT IN (
                               SELECT DISTINCT member_id FROM memberships WHERE status='active'
                           )""")
        db.close()
    except:
        pass

# ─── CLI: Initialize DB ───────────────────────────────────────────────────────
@app.cli.command('init-db')
def init_db():
    """Create tables and seed default data."""
    db = get_db()
    statements = [
        """CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            phone VARCHAR(20),
            join_date DATE NOT NULL,
            status ENUM('active','expired','inactive') DEFAULT 'active'
        )""",
        """CREATE TABLE IF NOT EXISTS trainers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            specialization VARCHAR(150),
            phone VARCHAR(20),
            email VARCHAR(150) UNIQUE NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS plans (
            id INT AUTO_INCREMENT PRIMARY KEY,
            plan_name VARCHAR(100) NOT NULL,
            duration_months INT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            description TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS memberships (
            id INT AUTO_INCREMENT PRIMARY KEY,
            member_id INT NOT NULL,
            plan_id INT NOT NULL,
            trainer_id INT,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            status ENUM('active','expired') DEFAULT 'active',
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
            FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            member_id INT NOT NULL,
            membership_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_date DATE NOT NULL,
            status ENUM('paid','pending') DEFAULT 'pending',
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
            FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS notices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            posted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id INT,
            FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `key` VARCHAR(100) UNIQUE NOT NULL,
            value TEXT
        )""",
    ]
    with db.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
            print(f'  OK: {stmt.strip().splitlines()[0][:60]}')

        # Seed default admin
        cur.execute("SELECT id FROM admins WHERE email='admin@gym.com'")
        if not cur.fetchone():
            h = generate_password_hash('admin123')
            cur.execute(
                "INSERT INTO admins (name,email,password_hash) VALUES ('Admin','admin@gym.com',%s)",
                (h,)
            )
            print('  Created default admin: admin@gym.com / admin123')
        else:
            print('  Admin already exists.')

        # Seed gym name setting
        cur.execute(
            "INSERT INTO settings (`key`,value) VALUES ('gym_name','FitZone Gym') "
            "ON DUPLICATE KEY UPDATE `key`=`key`"
        )

        # Seed sample plans
        cur.execute("SELECT id FROM plans LIMIT 1")
        if not cur.fetchone():
            sample_plans = [
                ('Basic Monthly',      1,  999.00, 'Access to gym floor and basic equipment'),
                ('Standard Quarterly', 3, 2499.00, 'Full gym access with locker facility'),
                ('Premium Half-Yearly',6, 4499.00, 'Full access + 1 personal training session/month'),
                ('Elite Annual',      12, 7999.00, 'Unlimited access + personal trainer + diet plan'),
            ]
            cur.executemany(
                "INSERT INTO plans (plan_name,duration_months,price,description) VALUES (%s,%s,%s,%s)",
                sample_plans
            )
            print('  Seeded 4 sample plans.')

    db.close()
    print('\nDatabase initialized successfully!')
    print('Login: admin@gym.com / admin123')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
