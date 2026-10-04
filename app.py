import os
import uuid
import base64
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Product, CartItem, Order, OrderItem, DeptYearPolicy, PasswordResetRequest

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# Jinja template filters
@app.template_filter('time_12hr')
def time_12hr(value):
    if not value:
        return ''

    try:
        if isinstance(value, str):
            value = value.strip()

            for fmt in (
                '%H:%M',
                '%H:%M:%S',
                '%I:%M %p',
                '%I:%M:%S %p'
            ):
                try:
                    return datetime.strptime(value, fmt).strftime('%I:%M %p')
                except ValueError:
                    continue

            return value

        return value.strftime('%I:%M %p')

    except Exception:
        return str(value)


@app.template_filter('datetime_12hr')
def datetime_12hr(value):
    if not value:
        return ''

    try:
        if isinstance(value, str):
            return value

        return value.strftime('%d-%m-%Y %I:%M %p')

    except Exception:
        return str(value)

# ---------------- HELPERS ----------------
def role_required(role):
    def decorator(f):
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                flash('Unauthorized access.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator


def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    )


def save_base64_image(data):
    try:
        if ',' in data:
            data = data.split(',', 1)[1]

        image_data = base64.b64decode(data)
        filename = f"selfie_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        with open(filepath, 'wb') as file:
            file.write(image_data)

        return os.path.join(
            'static', 'uploads', filename
        ).replace('\\', '/')
    except Exception:
        return None


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student_shop'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().upper()
        password = (request.form.get('password') or '').strip()

        # Find existing user
        user = User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first()

        # First-time student login
        # Example: B10001 / B10001
        if not user and re.match(r'^B\d{5}$', username):
            if password.upper() == username.upper():
                return render_template(
                    'login.html',
                    setup_required=True,
                    setup_username=username
                )

        # Check existing user password
        valid_password = False

        if user:
            if user.check_password(password):
                valid_password = True

            elif (
                user.role == 'student'
                and password.upper() == user.username.upper()
            ):
                user.set_password(user.username.upper())
                db.session.commit()
                valid_password = True

            elif (
                user.role == 'admin'
                and password in ['admin', 'admin123']
            ):
                user.set_password('admin123')
                db.session.commit()
                valid_password = True

        if user and valid_password:

            if user.role == 'student' and user.status == 'pending':
                flash(
                    'Your registration is pending approval by the Admin.',
                    'error'
                )
                return redirect(url_for('login'))

            elif user.role == 'student' and user.status == 'rejected':
                flash(
                    'Your registration request was rejected.',
                    'error'
                )
                return redirect(url_for('login'))

            # If student has not selected Course Level and Department
            if (
                user.role == 'student'
                and (
                    not user.department
                    or not user.year
                )
            ):
                return render_template(
                    'login.html',
                    setup_required=True,
                    setup_username=user.username
                )

            login_user(user)
            return redirect(url_for('index'))

        else:
            flash(
                'Invalid roll number or password. Please check your credentials.',
                'error'
            )

    return render_template(
        'login.html',
        setup_required=False
    )


@app.route('/student/first-setup', methods=['POST'])
def student_first_setup():

    username = (request.form.get('username') or '').strip().upper()
    year = request.form.get('year')
    department = request.form.get('department')

    # Available departments
    departments = {
        'UG': [
            'BCA',
            'BSc.COMPUTER SCIENCE',
            'B.COM',
            'BSc.MATHEMATICS',
            'BBA',
            'BA.ENGLISH',
            'BA.DEFENCE'
        ],
        'PG': [
            'MSc.COMPUTER SCIENCE',
            'MA.ENGLISH'
        ],
        'PhD': [
            'PhD COMPUTER SCIENCE',
            'PhD ENGLISH'
        ]
    }

    # Validate roll number
    if not re.match(r'^B\d{5}$', username):
        flash('Invalid Student Roll Number.', 'error')
        return redirect(url_for('login'))

    # Validate Course Level
    if year not in departments:
        flash('Please select a valid Course Level.', 'error')
        return redirect(url_for('login'))

    # Validate Department
    if department not in departments[year]:
        flash('Please select a valid Department.', 'error')
        return redirect(url_for('login'))

    # Check existing student
    user = User.query.filter(
        db.func.lower(User.username) == username.lower()
    ).first()

    if user:
        # Do not allow setup for pending/rejected accounts
        if user.status == 'pending':
            flash(
                'Your registration is pending approval by the Admin.',
                'error'
            )
            return redirect(url_for('login'))

        if user.status == 'rejected':
            flash(
                'Your registration request was rejected.',
                'error'
            )
            return redirect(url_for('login'))

        # Save Course Level and Department
        user.year = year
        user.department = department

    else:
        # Create new student account
        user = User(
            username=username,
            name=f"Student {username}",
            role='student',
            department=department,
            year=year,
            status='approved'
        )

        # First-time password = Roll Number
        user.set_password(username)

        db.session.add(user)

    db.session.commit()

    # Login student after setup
    login_user(user)

    return redirect(url_for('index'))
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        username = (request.form.get('username') or '').strip().upper()
        password = request.form.get('password')
        course_level = request.form.get('course_level')
        department = request.form.get('department')
        year = request.form.get('year')

        # Validate username
        if not re.match(r'^B\d{5}$', username):
            flash(
                'Student Roll Number / Username must start with "B" followed by 5 numbers (e.g. B10001).',
                'error'
            )
            return redirect(url_for('register'))

        # Check existing username
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash('Roll number / Username already exists.', 'error')
            return redirect(url_for('register'))

        # Validate Course Level
        if course_level not in ['UG', 'PG', 'PhD']:
            flash('Please select a valid Course Level.', 'error')
            return redirect(url_for('register'))

        # Validate Year
        if year not in ['1', '2', '3']:
            flash('Please select a valid Year.', 'error')
            return redirect(url_for('register'))

        # Department list
        departments = {
            'UG': [
                'BCA',
                'BSc.COMPUTER SCIENCE',
                'B.COM',
                'BSc.MATHEMATICS',
                'BBA',
                'BA.ENGLISH',
                'BA.DEFENCE'
            ],
            'PG': [
                'MSc.COMPUTER SCIENCE',
                'MA.ENGLISH'
            ],
            'PhD': [
                'PhD COMPUTER SCIENCE',
                'PhD ENGLISH'
            ]
        }

        # Validate Department
        if department not in departments.get(course_level, []):
            flash('Please select a valid Department.', 'error')
            return redirect(url_for('register'))

        # -----------------------------
        # Save Selfie
        # -----------------------------
        selfie_path = None

        # Camera captured image
        selfie_base64 = request.form.get('selfie_base64')

        if selfie_base64:
            selfie_path = save_base64_image(selfie_base64)

        # Uploaded image
        elif 'selfie' in request.files:
            selfie_file = request.files['selfie']

            if selfie_file and selfie_file.filename != '':
                if allowed_file(selfie_file.filename):
                    filename = f"selfie_{uuid.uuid4().hex}_{secure_filename(selfie_file.filename)}"
                    filepath = os.path.join(
                        app.config['UPLOAD_FOLDER'],
                        filename
                    )

                    os.makedirs(
                        app.config['UPLOAD_FOLDER'],
                        exist_ok=True
                    )

                    selfie_file.save(filepath)

                    selfie_path = os.path.join(
                        'static',
                        'uploads',
                        filename
                    ).replace('\\', '/')
                else:
                    flash('Invalid selfie image format.', 'error')
                    return redirect(url_for('register'))

       

        # -----------------------------
        # Create Student
        # -----------------------------
        new_student = User(
            username=username,
            name=name,
            role='student',
            course_level=course_level,
            department=department,
            year=year,
            selfie_path=selfie_path,
            status='pending'
        )

        new_student.set_password(password)

        db.session.add(new_student)
        db.session.commit()

        flash(
            'Registration submitted successfully! Please wait for Admin approval before logging in.',
            'success'
        )

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---
@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    # Reports
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    # Financial aggregate
    sales_today = db.session.query(db.func.sum(Order.total_price)).filter(
        db.func.date(Order.created_at) == today, Order.payment_status == 'Paid'
    ).scalar() or 0.0
    
    sales_week = db.session.query(db.func.sum(Order.total_price)).filter(
        Order.created_at >= start_of_week, Order.payment_status == 'Paid'
    ).scalar() or 0.0
    
    count_today = Order.query.filter(
        db.func.date(Order.created_at) == today, Order.payment_status == 'Paid'
    ).count()
    
    count_week = Order.query.filter(
        Order.created_at >= start_of_week, Order.payment_status == 'Paid'
    ).count()
    
    pending_students = User.query.filter_by(role='student', status='pending').count()
    pending_password_requests = PasswordResetRequest.query.filter_by(status='pending').count()
    
    # Active orders (not completed yet)
    active_orders = Order.query.filter(
        Order.status != 'Completed', Order.payment_status == 'Paid'
    ).order_by(Order.created_at.desc()).all()
    
    active_orders_count = len(active_orders)
    
    return render_template('dashboard_admin.html', 
                           sales_today=sales_today, 
                           sales_week=sales_week, 
                           count_today=count_today,
                           count_week=count_week,
                           pending_students=pending_students,
                           pending_password_requests=pending_password_requests,
                           active_orders=active_orders,
                           active_orders_count=active_orders_count)

@app.route('/admin/products', methods=['GET', 'POST'])
@role_required('admin')
def admin_products():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = f"prod_{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = os.path.join('static', 'uploads', filename).replace('\\', '/')
                
        new_prod = Product(name=name, price=price, category=category, image_path=image_path)
        db.session.add(new_prod)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))
        
    products = Product.query.all()
    return render_template('admin_products.html', products=products)

@app.route('/admin/products/toggle/<int:product_id>', methods=['POST'])
@role_required('admin')
def toggle_product(product_id):
    prod = Product.query.get_or_404(product_id)
    prod.available = not prod.available
    db.session.commit()
    flash(f"Product availability set to {'In Stock' if prod.available else 'Out of Stock'}.", 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@role_required('admin')
def delete_product(product_id):
    prod = Product.query.get_or_404(product_id)
    db.session.delete(prod)
    db.session.commit()
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/students')
@role_required('admin')
def admin_students():
    pending_students = User.query.filter_by(role='student', status='pending').all()
    approved_students = User.query.filter_by(role='student', status='approved').all()
    return render_template('admin_students.html', 
                           pending_students=pending_students, 
                           approved_students=approved_students)

@app.route('/admin/students/approve/<int:student_id>/<action>', methods=['POST'])
@role_required('admin')
def admin_approve_student(student_id, action):
    student = User.query.get_or_404(student_id)
    if action == 'approve':
        student.status = 'approved'
        flash(f"Approved registration for {student.name}.", 'success')
    else:
        student.status = 'rejected'
        flash(f"Rejected registration for {student.name}.", 'warning')
    db.session.commit()
    return redirect(url_for('admin_students'))

@app.route('/admin/students/add', methods=['POST'])
@role_required('admin')
def admin_add_student():

    name = (request.form.get('name') or '').strip()

    username = (request.form.get('username') or '').strip().upper()

    password = request.form.get('password')

    course_level = request.form.get('course_level')

    department = request.form.get('department')

    year = request.form.get('year')

    
    # Validate student username format: starts with 'B', followed by 5 numbers (e.g. B10001)
    if not re.match(r'^B\d{5}$', username):
        flash('Student Roll Number / Username must start with "B" followed by 5 numbers (e.g. B10001).', 'error')
        return redirect(url_for('admin_students'))
        
    # Check if exists
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash('Username already exists.', 'error')
        return redirect(url_for('admin_students'))
        
    student = User(
    name=name,
    username=username,
    role='student',
    course_level=course_level,
    department=department,
    year=year,
    status='approved'
)
    student.set_password(password)
    db.session.add(student)
    db.session.commit()
    
    flash(f"Student account created for {name}.", 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def admin_delete_student(student_id):
    student = User.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('Student account deleted.', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/orders')
@role_required('admin')
def admin_orders():
    status_filter = request.args.get('status', 'All')
    if status_filter != 'All':
        orders = Order.query.filter_by(status=status_filter).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders, current_filter=status_filter)

@app.route('/order/update-status/<int:order_id>', methods=['POST'])
@role_required('admin')
def update_order_status(order_id):
        
    new_status = request.form.get('status')
    order = Order.query.get_or_404(order_id)
    order.status = new_status
    if new_status == 'Rejected':
        order.rejection_notes = request.form.get('rejection_notes', 'Order could not be fulfilled.')
    db.session.commit()
    flash(f"Order {order.order_number} status updated to {new_status}.", 'success')
    
    redirect_to = request.form.get('redirect_to', 'index')
    return redirect(url_for(redirect_to))

# --- ADMIN PASSWORD & PERMISSION ROUTES ---
@app.route('/admin/passwords', methods=['GET', 'POST'])
@role_required('admin')
def admin_passwords():
    policies = DeptYearPolicy.query.order_by(DeptYearPolicy.department, DeptYearPolicy.year).all()
    pending_requests = PasswordResetRequest.query.filter_by(status='pending').order_by(PasswordResetRequest.created_at.desc()).all()
    approved_students = User.query.filter_by(role='student', status='approved').order_by(User.department, User.year, User.name).all()
    
    return render_template(
        'admin_passwords.html',
        policies=policies,
        pending_requests=pending_requests,
        approved_students=approved_students
    )

@app.route('/admin/passwords/policy/toggle/<int:policy_id>', methods=['POST'])
@role_required('admin')
def admin_toggle_password_policy(policy_id):
    policy = DeptYearPolicy.query.get_or_404(policy_id)
    policy.allow_password_change = not policy.allow_password_change
    db.session.commit()
    status_text = "ENABLED" if policy.allow_password_change else "RESTRICTED (Requires Admin Approval)"
    flash(f"Password change permission for {policy.department} - {policy.year} set to {status_text}.", 'success')
    return redirect(url_for('admin_passwords'))

@app.route('/admin/passwords/policy/add', methods=['POST'])
@role_required('admin')
def admin_add_password_policy():
    department = request.form.get('department')
    year = request.form.get('year')
    allow = request.form.get('allow_password_change') == 'true'
    notes = request.form.get('notes', '')

    existing = DeptYearPolicy.query.filter_by(department=department, year=year).first()
    if existing:
        existing.allow_password_change = allow
        existing.notes = notes
        flash(f"Updated policy rule for {department} - {year}.", 'success')
    else:
        new_pol = DeptYearPolicy(department=department, year=year, allow_password_change=allow, notes=notes)
        db.session.add(new_pol)
        flash(f"Added new password change policy for {department} - {year}.", 'success')
    
    db.session.commit()
    return redirect(url_for('admin_passwords'))

@app.route('/admin/passwords/request/<int:req_id>/<action>', methods=['POST'])
@role_required('admin')
def admin_handle_password_request(req_id, action):
    req_item = PasswordResetRequest.query.get_or_404(req_id)
    if action == 'approve':
        req_item.status = 'approved'
        user = User.query.get(req_item.user_id)
        if user:
            user.password_hash = req_item.requested_password_hash
            flash(f"Approved password change request for student {user.name} ({user.username}). Password updated.", 'success')
    else:
        req_item.status = 'rejected'
        flash(f"Rejected password change request for {req_item.student_name}.", 'warning')
    
    db.session.commit()
    return redirect(url_for('admin_passwords'))

@app.route('/admin/passwords/reset-direct', methods=['POST'])
@role_required('admin')
def admin_reset_student_password_direct():
    student_id = request.form.get('student_id')
    new_password = request.form.get('new_password')
    
    student = User.query.get_or_404(student_id)
    if not new_password or len(new_password.strip()) < 4:
        flash("Password must be at least 4 characters long.", 'error')
        return redirect(url_for('admin_passwords'))
        
    student.set_password(new_password)
    db.session.commit()
    flash(f"Successfully reset password for student {student.name} ({student.username}).", 'success')
    return redirect(url_for('admin_passwords'))

# --- STUDENT ROUTES ---
@app.route('/student/change-password', methods=['GET', 'POST'])
@role_required('student')
def student_change_password():
    policy_allowed = current_user.can_change_password()
    pending_request = PasswordResetRequest.query.filter_by(user_id=current_user.id, status='pending').first()

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        reason = request.form.get('reason', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('student_change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('student_change_password'))

        if len(new_password) < 4:
            flash('New password must be at least 4 characters long.', 'error')
            return redirect(url_for('student_change_password'))

        if policy_allowed:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Your password has been updated successfully!', 'success')
            return redirect(url_for('student_change_password'))
        else:
            if pending_request:
                flash('You already have a pending password change request awaiting Admin approval.', 'warning')
                return redirect(url_for('student_change_password'))

            from werkzeug.security import generate_password_hash
            new_hash = generate_password_hash(new_password)
            
            pwd_req = PasswordResetRequest(
                user_id=current_user.id,
                student_name=current_user.name or current_user.username,
                username=current_user.username,
                department=current_user.department or 'N/A',
                year=current_user.year or 'N/A',
                requested_password_hash=new_hash,
                reason=reason,
                status='pending'
            )
            db.session.add(pwd_req)
            db.session.commit()
            flash('Password change request submitted! Admin approval is required for your department and year.', 'info')
            return redirect(url_for('student_change_password'))

    return render_template(
        'student_change_password.html',
        policy_allowed=policy_allowed,
        pending_request=pending_request
    )

@app.route('/shop')
@role_required('student')
def student_shop():
    category = request.args.get('category', 'All')
    if category != 'All':
        products = Product.query.filter_by(category=category, available=True).all()
    else:
        products = Product.query.filter_by(available=True).all()
        
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    cart_total = sum(item.product.price * item.quantity for item in cart_items)
    
    return render_template('student_shop.html', 
                           products=products, 
                           cart_items=cart_items, 
                           cart_total=cart_total,
                           current_category=category)

@app.route('/cart/add', methods=['POST'])
@role_required('student')
def cart_add():
    data = request.get_json()
    product_id = data.get('product_id')
    
    # Check if item exists in cart
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)
        
    db.session.commit()
    return jsonify({'success': True})

@app.route('/cart/update', methods=['POST'])
@role_required('student')
def cart_update():
    data = request.get_json()
    item_id = data.get('cart_item_id')
    qty = data.get('quantity')
    
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    item.quantity = qty
    db.session.commit()
    return jsonify({'success': True})

@app.route('/cart/remove', methods=['POST'])
@role_required('student')
def cart_remove():
    data = request.get_json()
    item_id = data.get('cart_item_id')
    
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/checkout', methods=['POST'])
@role_required('student')
def student_checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('student_shop'))
        
    delivery_time = request.form.get('delivery_time')
    student_notes = request.form.get('student_notes')
    # Create an order in "Pending" status and pass to simulated PayU
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    order_number = f"TL-{uuid.uuid4().hex[:6].upper()}-{datetime.utcnow().strftime('%M%S')}"
    
    # Redirect student to simulated PayU portal
    return render_template('payu_mock.html', order_number=order_number, total_price=total_price, delivery_time=delivery_time, student_notes=student_notes)

@app.route('/payment/process', methods=['POST'])
@role_required('student')
def student_process_payment():
    outcome = request.form.get('outcome')
    order_number = request.form.get('order_number')
    delivery_time = request.form.get('delivery_time')
    student_notes = request.form.get('student_notes')
    
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Cart session expired.', 'error')
        return redirect(url_for('student_shop'))
        
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    
    if outcome == 'success':
        # Create final Order
        order = Order(
            order_number=order_number,
            user_id=current_user.id,
            total_price=total_price,
            status='Ordered',
            payment_status='Paid',
            delivery_time=delivery_time,
            student_notes=student_notes,
            payment_id=f"PAYU-{uuid.uuid4().hex[:8].upper()}"
        )
        db.session.add(order)
        
        # Add order items
        for item in cart_items:
            order_item = OrderItem(
                order=order,
                product_id=item.product_id,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity
            )
            db.session.add(order_item)
            
        # Empty student cart
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        flash(f"Payment successful! Order {order_number} has been placed.", 'success')
        return redirect(url_for('student_orders'))
    else:
        flash('Payment transaction failed on PayU. Please try again.', 'error')
        return redirect(url_for('student_shop'))

@app.route('/orders')
@role_required('student')
def student_orders():
    # Active orders
    active_orders = Order.query.filter(
        Order.user_id == current_user.id, 
        Order.status != 'Completed'
    ).order_by(Order.created_at.desc()).all()
    
    # Past completed orders
    order_history = Order.query.filter(
        Order.user_id == current_user.id, 
        Order.status == 'Completed'
    ).order_by(Order.created_at.desc()).all()
    
    return render_template('student_orders.html', active_orders=active_orders, order_history=order_history)

@app.route('/admin/reports')
@role_required('admin')
def admin_reports():
    # 1. Student distribution
    years = ['1st Year', '2nd Year', '3rd Year']
    student_counts = {}

    for yr in years:
        student_counts[yr] = User.query.filter_by(
            role='student',
            status='approved',
            year=yr
        ).count()

    selected_year = request.args.get('year', 'All')

    if selected_year != 'All':
        students = User.query.filter_by(
            role='student',
            status='approved',
            year=selected_year
        ).all()
    else:
        students = User.query.filter_by(
            role='student',
            status='approved'
        ).all()

    # 2. General sales statistics
    total_sales = db.session.query(
        db.func.sum(Order.total_price)
    ).filter_by(
        payment_status='Paid'
    ).scalar() or 0.0

    total_orders = Order.query.count()

    completed_orders = Order.query.filter_by(
        status='Completed'
    ).count()

    avg_order_value = (
        total_sales / total_orders
        if total_orders > 0
        else 0.0
    )

    # 3. Product sales popularity
    popular_items = db.session.query(
        OrderItem.product_name,
        db.func.sum(OrderItem.quantity).label('total_qty'),
        db.func.sum(
            OrderItem.price * OrderItem.quantity
        ).label('total_rev')
    ).group_by(
        OrderItem.product_name
    ).order_by(
        db.desc('total_qty')
    ).all()

    # 4. Historical Orders filters
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    product_search = request.args.get('product_search', '').strip()

    query = Order.query

    # Product search
    if product_search:
        matching_order_ids = db.session.query(
            OrderItem.order_id
        ).filter(
            OrderItem.product_name.ilike(
                f"%{product_search}%"
            )
        ).subquery()

        query = query.filter(
            Order.id.in_(matching_order_ids)
        )

    # From date
    if start_date_str:
        try:
            start_date = datetime.strptime(
                start_date_str,
                "%Y-%m-%d"
            )
            query = query.filter(
                Order.created_at >= start_date
            )
        except ValueError:
            pass

    # To date
    if end_date_str:
        try:
            end_date = datetime.strptime(
                end_date_str,
                "%Y-%m-%d"
            )
            query = query.filter(
                Order.created_at <
                end_date + timedelta(days=1)
            )
        except ValueError:
            pass

    historical_orders = query.order_by(
        Order.created_at.desc()
    ).all()
   

    return render_template(
        'admin_reports.html',
        student_counts=student_counts,
        students=students,
        selected_year=selected_year,
        total_sales=total_sales,
        total_orders=total_orders,
        completed_orders=completed_orders,
        avg_order_value=avg_order_value,
        popular_items=popular_items,
        historical_orders=historical_orders,
        start_date=start_date_str,
        end_date=end_date_str,
        product_search=product_search
    )            

@app.route('/api/notifications')
@login_required
def api_notifications():
    if current_user.role == 'student':
        active_orders = Order.query.filter(
            Order.user_id == current_user.id,
            Order.status != 'Completed'
        ).all()
        orders_data = [{'order_number': o.order_number, 'status': o.status} for o in active_orders]
        return jsonify({
            'role': 'student',
            'orders': orders_data
        })
    elif current_user.role == 'admin':
        pending_count = User.query.filter_by(role='student', status='pending').count()
        pending_pwd_count = PasswordResetRequest.query.filter_by(status='pending').count()
        active_orders = Order.query.filter(
            Order.status != 'Completed',
            Order.payment_status == 'Paid'
        ).all()
        orders_data = [{'order_number': o.order_number, 'status': o.status} for o in active_orders]
        return jsonify({
            'role': 'admin',
            'pending_approvals': pending_count,
            'pending_password_requests': pending_pwd_count,
            'active_orders': orders_data
        })
    return jsonify({'role': 'none'})
# --- DATABASE INITIALIZATION ---
with app.app_context():
    db.create_all()



# --- RUN APPLICATION ---
if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )

