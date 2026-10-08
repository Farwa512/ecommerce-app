from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import os
import stripe
from models import db, Product, User, Order, OrderItem

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://ecom_user:Shop1234@localhost/ecommerce_db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SECRET_KEY'] = 'change-this-to-any-random-text'
db.init_app(app)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def parse_cart_key(key):
    parts = key.split('|')
    product_id = int(parts[0])
    size = parts[1] if len(parts) > 1 else ''
    color = parts[2] if len(parts) > 2 else ''
    return product_id, size, color


def option_text(size, color):
    parts = []
    if size:
        parts.append('Size: ' + size)
    if color:
        parts.append('Color: ' + color)
    return ', '.join(parts)


with app.app_context():
    db.create_all()


@app.route('/')
def index():
    products = Product.query.filter_by(is_active=True).all()
    return render_template('index.html', products=products)


@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.filter_by(id=id, is_active=True).first_or_404()
    return render_template('product_detail.html', product=product)


@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category = request.form.get('category', '')
        sizes = request.form.get('sizes', '')
        colors = request.form.get('colors', '')

        image_file = request.files.get('image')
        filename = ''
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_product = Product(
            name=name,
            description=description,
            price=price,
            stock=stock,
            image=filename,
            category=category,
            sizes=sizes,
            colors=colors
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('admin/add_product.html')


@app.route('/admin/products')
@login_required
@admin_required
def manage_products():
    products = Product.query.filter_by(is_active=True).all()
    return render_template('admin/manage_products.html', products=products)


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])
        product.category = request.form.get('category', '')
        product.sizes = request.form.get('sizes', '')
        product.colors = request.form.get('colors', '')
        db.session.commit()
        return redirect(url_for('manage_products'))
    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    flash(f'{product.name} has been removed.', 'success')
    return redirect(url_for('manage_products'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('This email is already registered.', 'danger')
            return redirect(url_for('register'))

        new_user = User(name=name, email=email,
                        password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))

        flash('Invalid email or password.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/cart/add/<int:product_id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    size = request.values.get('size', '').strip()
    color = request.values.get('color', '').strip()

    if product.stock <= 0:
        flash('This product is out of stock.', 'danger')
        return redirect(url_for('product_detail', id=product.id))

    if product.sizes:
        available_sizes = [s.strip() for s in product.sizes.split(',')]
        if size not in available_sizes:
            flash('Please select a size.', 'danger')
            return redirect(url_for('product_detail', id=product.id))
    else:
        size = ''

    if product.colors:
        available_colors = [c.strip() for c in product.colors.split(',')]
        if color not in available_colors:
            flash('Please select a color.', 'danger')
            return redirect(url_for('product_detail', id=product.id))
    else:
        color = ''

    key = f"{product.id}|{size}|{color}"
    cart = session.get('cart', {})
    cart[key] = cart.get(key, 0) + 1
    session['cart'] = cart
    flash(f'{product.name} added to cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/cart')
@login_required
def view_cart():
    cart = session.get('cart', {})
    items = []
    total = 0

    for key, quantity in cart.items():
        product_id, size, color = parse_cart_key(key)
        product = Product.query.get(product_id)
        if product:
            subtotal = product.price * quantity
            total += subtotal
            items.append({
                'key': key,
                'product': product,
                'quantity': quantity,
                'size': size,
                'color': color,
                'subtotal': subtotal
            })

    return render_template('cart.html', items=items, total=total)


@app.route('/cart/remove')
@login_required
def remove_from_cart():
    key = request.args.get('key', '')
    cart = session.get('cart', {})
    if key in cart:
        del cart[key]
        session['cart'] = cart
    return redirect(url_for('view_cart'))


@app.route('/checkout')
@login_required
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'danger')
        return redirect(url_for('view_cart'))

    line_items = []
    for key, quantity in cart.items():
        product_id, size, color = parse_cart_key(key)
        product = Product.query.get(product_id)
        if product:
            name = product.name
            options = option_text(size, color)
            if options:
                name = f"{product.name} ({options})"
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': name},
                    'unit_amount': int(product.price * 100),
                },
                'quantity': quantity,
            })

    checkout_session = stripe.checkout.Session.create(
        line_items=line_items,
        mode='payment',
        success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('view_cart', _external=True),
    )

    return redirect(checkout_session.url, code=303)


@app.route('/payment/success')
@login_required
def payment_success():
    session_id = request.args.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(session_id)

    if checkout_session.payment_status == 'paid':
        cart = session.get('cart', {})
        total = checkout_session.amount_total / 100

        new_order = Order(
            user_id=current_user.id,
            total=total,
            status='paid',
            stripe_session_id=session_id
        )
        db.session.add(new_order)
        db.session.commit()

        for key, quantity in cart.items():
            product_id, size, color = parse_cart_key(key)
            product = Product.query.get(product_id)
            if product:
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price=product.price,
                    size=size,
                    color=color
                )
                db.session.add(order_item)
                product.stock -= quantity

        db.session.commit()
        session['cart'] = {}

        flash('Payment successful! Your order has been placed.', 'success')
        return render_template('payment_success.html', order=new_order)

    flash('Payment was not completed.', 'danger')
    return redirect(url_for('view_cart'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
