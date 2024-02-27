from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
import datetime
import os

app = Flask(__name__)  # Initialize Flask app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Get directory of current file
db_path = os.path.join(BASE_DIR, "data", "my-budget.db")  # Create database path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path  # Set SQLAlchemy database URI
db = SQLAlchemy(app)  # Initialize SQLAlchemy with app

month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
year = datetime.datetime.now().year  # Get current year
month = datetime.datetime.now().month  # Get current month

class Entry(db.Model):  # Define Entry model
    id = db.Column(db.Integer, primary_key=True)
    bill_name = db.Column(db.String(80), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)

class PayPeriodForm(FlaskForm):  # Define PayPeriodForm form
    start_date = DateField('Start Date', format='%Y-%m-%d')
    end_date = DateField('End Date', format='%Y-%m-%d')
    submit = SubmitField('Sort')

with app.app_context():  # Create all tables in the database
    db.create_all()

def get_bills():  # Function to get all bills
    return Entry.query.all()

@app.route('/')
def home():
    bills = get_bills()  # Get all bills
    now = datetime.datetime.now()  # Get current date

    # Determine current and next pay periods
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

    # Calculate total due for this and next pay periods
    total_due_this_pay_period = sum(bill.amount_due for bill in bills if this_pay_period_start.date() <= bill.due_date <= this_pay_period_end.date())
    total_due_next_pay_period = sum(bill.amount_due for bill in bills if next_pay_period_start.date() <= bill.due_date <= next_pay_period_end.date())

    # Render template with bills and pay period dates
    return render_template('index.html', bills=bills, now=now,
                            this_pay_period_start=this_pay_period_start,
                            this_pay_period_end=this_pay_period_end, 
                            next_pay_period_start=next_pay_period_start, 
                            next_pay_period_end=next_pay_period_end,
                            total_due_this_pay_period=total_due_this_pay_period,
                            total_due_next_pay_period=total_due_next_pay_period)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    entry = Entry.query.get_or_404(id)  # Query for the entry with the given id
    if request.method == 'POST':
        due_date = request.form.get('due_date')  # Get the due_date from the form
        bill_name = request.form.get('bill_name')  # Get the bill_name from the form
        amount_due = request.form.get('amount_due')  # Get the amount_due from the form

        if not due_date or not bill_name or not amount_due:  # Check if any of the fields are empty
            return "Error: All fields are required", 400

        due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()  # Convert due_date to datetime object

        entry.due_date = due_date  # Update the due_date of the entry
        entry.bill_name = bill_name  # Update the bill_name of the entry
        entry.amount_due = amount_due  # Update the amount_due of the entry

        db.session.commit()  # Commit the changes to the database

        year = due_date.year  # Get the year from the due_date
        month = due_date.month  # Get the month from the due_date
        return redirect(url_for('month_view', year=year, month=month))  # Redirect back to the same month page
    
    year = entry.due_date.year  # Get the year from the entry's due_date
    month = entry.due_date.month  # Get the month from the entry's due_date
    years = [row[0] for row in db.session.query(db.extract('year', Entry.due_date)).distinct().all()]  # Get distinct years from the entries
    return render_template('edit.html', entry=entry, years=years, year=year, month=month)  # Render the edit page with the entry and years

@app.route('/confirm_edit/<int:id>', methods=['POST'])
def confirm_edit(id):
    entry = Entry.query.get_or_404(id)  # Query for the entry with the given id

    due_date = request.form.get('due_date')  # Get the due_date from the form
    due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()  # Convert due_date to datetime object
    bill_name = request.form.get('bill_name')  # Get the bill_name from the form
    amount_due = request.form.get('amount_due')  # Get the amount_due from the form

    entry.due_date = due_date  # Update the due_date of the entry
    entry.bill_name = bill_name  # Update the bill_name of the entry
    entry.amount_due = amount_due  # Update the amount_due of the entry

    db.session.commit()  # Commit the changes to the database

    year = due_date.year  # Get the year from the due_date
    month = due_date.month  # Get the month from the due_date
    return redirect(url_for('month_view', year=year, month=month))  # Redirect to the home page

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    entry = Entry.query.get_or_404(id)  # Query for the entry with the given id

    if request.method == 'POST':
        db.session.delete(entry)  # Delete the entry from the database
        db.session.commit()  # Commit the changes to the database
        return redirect(url_for('home'))  # Redirect to the home page

    return render_template('delete.html', id=id, entry=entry)  # Render the delete page with the entry

@app.route('/<int:year>/<int:month>/', methods=['GET', 'POST'])
def month_view(year, month):
    if request.method == 'POST':
        due_date = request.form.get('due_date')  # Get the due_date from the form
        bill_name = request.form.get('bill_name')  # Get the bill_name from the form
        amount_due = request.form.get('amount_due')  # Get the amount_due from the form

        if not due_date or not bill_name or not amount_due:  # Check if any of the fields are empty
            return "Error: All fields are required", 400

        due_date = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()  # Convert due_date to datetime object

        entry = Entry(due_date=due_date, bill_name=bill_name, amount_due=amount_due)  # Create a new entry

        db.session.add(entry)  # Add the new entry to the database
        db.session.commit()  # Commit the changes to the database

        year = due_date.year  # Get the year from the due_date
        month = due_date.month  # Get the month from the due_date
        return redirect(url_for('month_view', year=year, month=month))  # Redirect back to the same month page
    
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']  # Define month_names

    entries = Entry.query.filter(db.extract('year', Entry.due_date) == year, db.extract('month', Entry.due_date) == month).order_by(Entry.due_date).all()  # Query entries for the specified month and year

    total_due = sum(entry.amount_due for entry in entries)  # Calculate total amount due

    years = db.session.query(db.extract('year', Entry.due_date).label('year')).distinct().all()  # Query distinct years from the database

    now = datetime.datetime.now()  # Get the current date and time
    return render_template('month.html', now=now, entries=entries, year=year, month=month, month_names=month_names, years=years, total_due=total_due)  # Render the month page with the entries, year, month, month_names, years, and total_due

# @app.route('/pay_period/', methods=['GET'])
# def pay_period_view():
#     form = PayPeriodForm(request.form)
#     if form.validate_on_submit():
#         start_date = form.start_date.data
#         end_date = form.end_date.data

#         # Query entries for the specified pay period and sort them by due date
#         entries = Entry.query.filter(Entry.due_date.between(start_date, end_date)).order_by(Entry.due_date).all()

#         # Calculate total amount due
#         total_due = sum(entry.amount_due for entry in entries)

#         return render_template('pay_period.html', entries=entries, start_date=start_date, end_date=end_date, total_due=total_due)