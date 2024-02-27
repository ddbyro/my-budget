# app.py
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
import datetime
import os


# Initialize the Flask application
app = Flask(__name__)

# Get the absolute path of the directory of the current file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Create the path to the database file
db_path = os.path.join(BASE_DIR, "data", "my-budget.db")

# Use the path in the SQLAlchemy database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://///app/data/my-budget.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://///./data/my-budget.db'
db = SQLAlchemy(app)
month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
year = datetime.datetime.now().year
month = datetime.datetime.now().month


# List to store entries
entries = []


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_name = db.Column(db.String(80), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)


class PayPeriodForm(FlaskForm):
    start_date = DateField('Start Date', format='%Y-%m-%d')
    end_date = DateField('End Date', format='%Y-%m-%d')
    submit = SubmitField('Sort')

# Create all tables in the database which do not exist yet
with app.app_context():
    db.create_all()


# @app.route('/', methods=['GET', 'POST'])
# def home():
#     # Redirect to the month_view function
#     year = datetime.datetime.now().year
#     month = datetime.datetime.now().month
#     return redirect(url_for('month_view', year=year, month=month))


def get_bills():
    return Entry.query.all()

@app.route('/')
def home():
    # Get the list of bills from the database
    bills = get_bills()  

    # Get the current date
    now = datetime.datetime.now()

    # Determine the current and next pay periods
    if now.day <= 15:
        this_pay_period_start = datetime.datetime(now.year, now.month, 1)
        this_pay_period_end = datetime.datetime(now.year, now.month, 15)
        next_pay_period_start = datetime.datetime(now.year, now.month, 16)
        next_pay_period_end = datetime.datetime(now.year, now.month + 1, 1) - datetime.timedelta(days=1)
    else:
        this_pay_period_start = datetime.datetime(now.year, now.month, 16)
        this_pay_period_end = datetime.datetime(now.year, now.month + 1, 1) - datetime.timedelta(days=1)
        next_pay_period_start = datetime.datetime(now.year, now.month + 1, 1)
        next_pay_period_end = datetime.datetime(now.year, now.month + 1, 15)

    # Calculate the total amount due this pay period
    total_due_this_pay_period = sum(bill.amount_due for bill in bills if this_pay_period_start.date() <= bill.due_date <= this_pay_period_end.date())

    # Calculate the total amount due next pay period
    total_due_next_pay_period = sum(bill.amount_due for bill in bills if next_pay_period_start.date() <= bill.due_date <= next_pay_period_end.date())
    

    # Render the index.html template and pass the bills and pay period dates to it
    return render_template('index.html', bills=bills, now=now,
                            this_pay_period_start=this_pay_period_start,
                            this_pay_period_end=this_pay_period_end, 
                            next_pay_period_start=next_pay_period_start, 
                            next_pay_period_end=next_pay_period_end,
                            total_due_this_pay_period=total_due_this_pay_period,
                            total_due_next_pay_period=total_due_next_pay_period)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    entry = Entry.query.get_or_404(id)
    if request.method == 'POST':
        due_date = request.form.get('due_date')
        bill_name = request.form.get('bill_name')
        amount_due = request.form.get('amount_due')

        # Check if any of the fields are empty
        if not due_date or not bill_name or not amount_due:
            return "Error: All fields are required", 400

        # Print the form data
        print(f"Form data: {due_date}, {bill_name}, {amount_due}")

        due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()

        entry.due_date = due_date
        entry.bill_name = bill_name
        entry.amount_due = amount_due

        # Print the updated entry
        print(f"Updated entry: {entry}")

        db.session.commit()

        # Print a message after committing the session
        print("Session committed")

        # Redirect back to the same month page
        year = due_date.year
        month = due_date.month
        return redirect(url_for('month_view', year=year, month=month))
    
    year = entry.due_date.year
    month = entry.due_date.month
    years = [row[0] for row in db.session.query(db.extract('year', Entry.due_date)).distinct().all()]
    return render_template('edit.html', entry=entry, years=years, year=year, month=month)


@app.route('/confirm_edit/<int:id>', methods=['POST'])
def confirm_edit(id):
    # Query the database for the entry with the given id
    entry = Entry.query.get_or_404(id)

    # Get the form data
    due_date = request.form.get('due_date')
    due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()
    bill_name = request.form.get('bill_name')
    amount_due = request.form.get('amount_due')

    # Update the entry
    entry.due_date = due_date
    entry.bill_name = bill_name
    entry.amount_due = amount_due

    # Commit the session
    db.session.commit()

    # Redirect to the home page
    year = due_date.year
    month = due_date.month
    return redirect(url_for('month_view', year=year, month=month))

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    entry = Entry.query.get_or_404(id)

    if request.method == 'POST':
        db.session.delete(entry)
        db.session.commit()
        return redirect(url_for('home'))

    return render_template('delete.html', id=id, entry=entry)


@app.route('/<int:year>/<int:month>/', methods=['GET', 'POST'])
def month_view(year, month):
    if request.method == 'POST':
        due_date = request.form.get('due_date')
        bill_name = request.form.get('bill_name')
        amount_due = request.form.get('amount_due')

        # Check if any of the fields are empty
        if not due_date or not bill_name or not amount_due:
            return "Error: All fields are required", 400

        # Print the form data
        print(f"Form data: {due_date}, {bill_name}, {amount_due}")

        due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()

        # Create a new entry
        entry = Entry(due_date=due_date, bill_name=bill_name, amount_due=amount_due)

        # Print the updated entry
        print(f"Updated entry: {entry}")

        db.session.add(entry)
        db.session.commit()

        # Print a message after committing the session
        print("Session committed")

        # Redirect back to the same month page
        year = due_date.year
        month = due_date.month
        return redirect(url_for('month_view', year=year, month=month))
    
    
    # Define month_names
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

    # Query entries for the specified month and year
    entries = Entry.query.filter(db.extract('year', Entry.due_date) == year, db.extract('month', Entry.due_date) == month).order_by(Entry.due_date).all()
    print(entries)
    # Calculate total amount due
    total_due = sum(entry.amount_due for entry in entries)

    # Query distinct years from the database
    years = db.session.query(db.extract('year', Entry.due_date).label('year')).distinct().all()

    now = datetime.datetime.now()
    return render_template('month.html', now=now, entries=entries, year=year, month=month, month_names=month_names, years=years, total_due=total_due)


@app.route('/pay_period/', methods=['GET'])
def pay_period_view():
    form = PayPeriodForm(request.form)
    if form.validate_on_submit():
        start_date = form.start_date.data
        end_date = form.end_date.data

        # Query entries for the specified pay period and sort them by due date
        entries = Entry.query.filter(Entry.due_date.between(start_date, end_date)).order_by(Entry.due_date).all()

        # Calculate total amount due
        total_due = sum(entry.amount_due for entry in entries)

        return render_template('pay_period.html', entries=entries, start_date=start_date, end_date=end_date, total_due=total_due)