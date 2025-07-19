from flask import Flask, render_template, request, redirect, url_for
from models import db, Product, Batch, Sale, SaleItem

app = Flask(__name__)

# ✅ Initialize only ONCE
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/aiml_project'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # ✅ only one place

# ✅ Create tables inside DB
with app.app_context():
    db.create_all()

# ... your Flask routes start here


# ✅ Home route
@app.route('/')
def home():
    return render_template('base.html')

# ✅ View all products
@app.route('/products')
def view_products():
    products = Product.query.all()
    return render_template('products.html', products=products)

# ✅ Add new product
@app.route('/products/new', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        unit_price = request.form['unit_price']
        quantity = request.form['quantity']
        
        product = Product(
            name=name,
            description=description,
            unit_price=float(unit_price),
            quantity=int(quantity)
        )
        db.session.add(product)
        db.session.commit()
        return redirect('/products')
    
    return render_template('product_form.html')



# Edit a product
@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.unit_price = request.form['unit_price']
        product.quantity = request.form['quantity']
        db.session.commit()
        return redirect('/products')
    return render_template('product_form.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect('/dashboard')



@app.route('/add_batch', methods=['GET', 'POST'])
def add_batch():
    if request.method == 'POST':
        product_id = request.form['product_id']
        quantity = request.form['quantity']
        batch = Batch(product_id=product_id, quantity=quantity)
        db.session.add(batch)
        db.session.commit()
        return redirect('/inventory')

    products = Product.query.all()
    return render_template('add_batch.html', products=products)

@app.route('/inventory')
def view_inventory():
    batches = Batch.query.all()
    return render_template('inventory.html', batches=batches)


@app.route('/billing', methods=['GET', 'POST'])
def billing():
    products = Product.query.all()

    if request.method == 'POST':
        selected_items = []
        total = 0
        customer_email = request.form['email']

        for product in products:
            qty = int(request.form.get(f'quantity_{product.id}', 0))
            if qty > 0:
                line_total = qty * product.unit_price
                total += line_total
                selected_items.append((product, qty, line_total))

        tax = total * 0.18  # 18% GST
        discount = total * 0.10  # Optional: 10% discount
        final_total = total + tax - discount

        # Save to DB
        sale = Sale(total_amount=total, tax=tax, discount=discount, final_amount=final_total)
        db.session.add(sale)
        db.session.commit()

        for product, qty, line_total in selected_items:
            item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=qty,
                price_per_unit=product.unit_price
            )
            db.session.add(item)
            product.quantity -= qty  # Decrease inventory

        db.session.commit()

        # ✅ Email recommendations logic
        from collections import defaultdict
        from itertools import combinations
        import smtplib
        from email.mime.text import MIMEText

        # Build co-purchase map
        sales = Sale.query.all()
        recommendations_map = defaultdict(lambda: defaultdict(int))
        for s in sales:
            basket = [i.product.name for i in s.items]
            for a, b in combinations(set(basket), 2):
                recommendations_map[a][b] += 1
                recommendations_map[b][a] += 1

        # Generate recommendations for purchased items
        recommended_products = []
        for product, _, _ in selected_items:
            related = recommendations_map.get(product.name, {})
            if related:
                best_match = max(related.items(), key=lambda x: x[1])[0]
                recommended_products.append(best_match)

        recommended_products = list(set(recommended_products))  # Remove duplicates

        # ✅ Send email
        if customer_email and recommended_products:
            try:
                # Prepare the email body
                message = "Hi there,\n\nThank you for your purchase!\n\nBased on your order, you may also like:\n"
                for r in recommended_products:
                    message += f"- {r}\n"

                message += "\nHappy Shopping!\nTeam Tantrata"

                # Compose the email
                msg = MIMEText(message)
                msg["Subject"] = "🛍️ Product Recommendations Just for You"
                msg["From"] = "omgautam382@gmail.com"
                msg["To"] = customer_email

                # Send email via Gmail SMTP
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login("omgautam382@gmail.com", "gpkuwlhvvtfgutqm")  # App password
                    server.send_message(msg)

                print("📨 Recommendation email sent to:", customer_email)

            except Exception as e:
                print("❌ Failed to send email:", str(e))

        # ✅ Always return the invoice page after POST
        return render_template('invoice.html', sale=sale, items=selected_items)

    # GET method: show billing form
    return render_template('billing.html', products=products)


@app.route('/dashboard')
def dashboard():
    products = Product.query.all()
    inventory = Batch.query.all()
    sale_items = SaleItem.query.all()

    # ---------- Forecasting Logic ----------
    import pandas as pd
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import IsolationForest

    forecast_result = []
    forecast_data = []

    for item in sale_items:
        forecast_data.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'date': item.sale.date,
            'quantity': item.quantity
        })

    df = pd.DataFrame(forecast_data)

    if not df.empty:
        for product_id in df['product_id'].unique():
            sub_df = df[df['product_id'] == product_id]
            sub_df = sub_df.groupby('date').sum().reset_index()
            sub_df['day_num'] = (sub_df['date'] - sub_df['date'].min()).dt.days

            if len(sub_df) >= 2:
                model = LinearRegression()
                model.fit(sub_df[['day_num']], sub_df['quantity'])
                future_day = sub_df['day_num'].max() + 30
                predicted_qty = model.predict([[future_day]])[0]

                forecast_result.append({
                    'product_name': df[df['product_id'] == product_id]['product_name'].iloc[0],
                    'predicted_qty': round(predicted_qty)
                })

    # ---------- Anomaly Detection Logic ----------
    anomalies_found = []

    if not df.empty:
        for product_id in df['product_id'].unique():
            sub_df = df[df['product_id'] == product_id]
            sub_df = sub_df.groupby('date').sum().reset_index()

            if len(sub_df) >= 2:
                model = IsolationForest(contamination=0.2)
                sub_df['score'] = model.fit_predict(sub_df[['quantity']])

                for _, row in sub_df[sub_df['score'] == -1].iterrows():
                    anomalies_found.append({
                        'product_name': df[df['product_id'] == product_id]['product_name'].iloc[0],
                        'date': row['date'],
                        'quantity': row['quantity']
                    })

    # ---------- Price Optimization Logic ----------
    price_df = []
    for item in sale_items:
        price_df.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'price': item.price_per_unit,
            'quantity': item.quantity
        })

    price_df = pd.DataFrame(price_df)
    optimal_prices = []

    if not price_df.empty:
        for product_id in price_df['product_id'].unique():
            sub_df = price_df[price_df['product_id'] == product_id]
            if len(sub_df) >= 5:
                X = sub_df[['price']]
                y = sub_df['quantity']
                model = LinearRegression()
                model.fit(X, y)

                price_range = list(range(int(X['price'].min()), int(X['price'].max()) + 5))
                best_price = max(price_range, key=lambda p: model.predict([[p]])[0])

                optimal_prices.append({
                    'product_name': sub_df['product_name'].iloc[0],
                    'optimal_price': best_price
                })

    # ---------- Inventory Optimization Logic ----------
    inventory_suggestions = []

    if not df.empty:
        for product_id in df['product_id'].unique():
            sub_df = df[df['product_id'] == product_id]
            sub_df = sub_df.groupby('date').sum().reset_index()
            sub_df['day_num'] = (sub_df['date'] - sub_df['date'].min()).dt.days

            if len(sub_df) >= 5:
                model = LinearRegression()
                model.fit(sub_df[['day_num']], sub_df['quantity'])
                next_7_day = sub_df['day_num'].max() + 7
                predicted_demand = model.predict([[next_7_day]])[0]

                inventory_suggestions.append({
                    'product_name': df[df['product_id'] == product_id]['product_name'].iloc[0],
                    'recommended_qty': round(predicted_demand)
                })

    # ---------- Final Render ----------
    return render_template(
        'dashboard.html',
        products=products,
        inventory=inventory,
        forecast_result=forecast_result,
        anomalies=anomalies_found,
        optimal_prices=optimal_prices,
        inventory_suggestions=inventory_suggestions
    )



@app.route('/download_invoice/<int:sale_id>')
def download_invoice(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    items = []
    for item in sale.items:
        line_total = item.quantity * item.price_per_unit
        items.append((item.product, item.quantity, line_total))

    html = render_template('invoice_pdf.html', sale=sale, items=items)
    result = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result)

    if pisa_status.err:
        return "Error generating PDF", 500

    response = make_response(result.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=invoice_{sale_id}.pdf'
    return response
import pandas as pd
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta

@app.route('/forecast')
def forecast():
    from sklearn.linear_model import LinearRegression
    import pandas as pd

    sale_items = SaleItem.query.all()

    # Build forecast data
    data = []
    for item in sale_items:
        data.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'date': item.sale.date,
            'quantity': item.quantity
        })

    df = pd.DataFrame(data)
    forecast_result = []

    if not df.empty:
        for product_id in df['product_id'].unique():
            sub_df = df[df['product_id'] == product_id]
            sub_df = sub_df.groupby('date').sum().reset_index()
            sub_df['day_num'] = (sub_df['date'] - sub_df['date'].min()).dt.days

            model = LinearRegression()
            model.fit(sub_df[['day_num']], sub_df['quantity'])

            future_day = sub_df['day_num'].max() + 30
            predicted_qty = model.predict([[future_day]])[0]

            forecast_result.append({
                'product_name': sub_df['product_name'].iloc[0],
                'predicted_qty': round(predicted_qty)
            })

    return render_template("forecast.html", forecast_result=forecast_result)

@app.route('/recommendations')
def recommendations():
    from collections import defaultdict
    from itertools import combinations

    # Get all sales
    sales = Sale.query.all()

    # Build a list of product IDs per sale
    sale_baskets = []
    for sale in sales:
        basket = [item.product.name for item in sale.items]
        if len(basket) > 1:
            sale_baskets.append(basket)

    # Count co-occurrences
    recommendations_map = defaultdict(lambda: defaultdict(int))
    for basket in sale_baskets:
        for prod1, prod2 in combinations(set(basket), 2):
            recommendations_map[prod1][prod2] += 1
            recommendations_map[prod2][prod1] += 1

    # Pick the top recommendation for each product
    final_recommendations = []
    for product, co_products in recommendations_map.items():
        recommended = max(co_products.items(), key=lambda x: x[1])[0]
        final_recommendations.append((product, recommended))

    return render_template("recommendations.html", recommendations=final_recommendations)

@app.route('/anomalies')
def anomalies():
    import pandas as pd
    from sklearn.ensemble import IsolationForest

    sale_items = SaleItem.query.all()
    data = []

    for item in sale_items:
        data.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'date': item.sale.date,
            'quantity': item.quantity
        })

    df = pd.DataFrame(data)
    anomalies_found = []

    if not df.empty:
        for product_id in df['product_id'].unique():
            sub_df = df[df['product_id'] == product_id]
            sub_df = sub_df.groupby('date').sum().reset_index()

            if len(sub_df) >= 5:  # We need enough data points to detect anomalies
                model = IsolationForest(contamination=0.2)
                sub_df['score'] = model.fit_predict(sub_df[['quantity']])

                for _, row in sub_df[sub_df['score'] == -1].iterrows():
                    anomalies_found.append({
                        'product_name': df[df['product_id'] == product_id]['product_name'].iloc[0],
                        'date': row['date'],
                        'quantity': row['quantity']
                    })

    return render_template("anomalies.html", anomalies=anomalies_found)

# ✅ Run the app
if __name__ == '__main__':
    app.run(debug=True)

