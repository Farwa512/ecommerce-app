from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
from models import db, Product

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://ecom_user:Shop1234@localhost/ecommerce_db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/admin/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
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
            image=filename
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('admin/add_product.html')

@app.route('/admin/products')
def manage_products():
    products = Product.query.all()
    return render_template('admin/manage_products.html', products=products)

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])
        db.session.commit()
        return redirect(url_for('manage_products'))
    return render_template('admin/edit_product.html', product=product)

@app.route('/admin/delete/<int:id>')
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('manage_products'))
if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=5000)
