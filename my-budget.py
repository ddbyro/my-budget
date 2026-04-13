from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
import calendar
import datetime
import os

app = Flask(__name__)  # Initialize Flask app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Get directory of current file
db_path = os.path.join(BASE_DIR, "data", "my-budget.db")  # Create database path
os.makedirs(os.path.dirname(db_path), exist_ok=True)  # Ensure data directory exists
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

class Config(db.Model):
    key   = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(200), nullable=False)


class PayPeriodForm(FlaskForm):  # Define PayPeriodForm form
    start_date = DateField('Start Date', format='%Y-%m-%d')
    end_date = DateField('End Date', format='%Y-%m-%d')
    submit = SubmitField('Sort')

with app.app_context():  # Create all tables in the database
    db.create_all()

def get_config(key, default=''):
    row = Config.query.get(key)
    return row.value if row else default


def set_config(key, value):
    row = Config.query.get(key)
    if row:
        row.value = value
    else:
        db.session.add(Config(key=key, value=value))
    db.session.commit()


def get_pay_period_dates(year, month, period):
    """Return (start_date, end_date) for a pay period. Period 1 = 1–15, period 2 = 16–end."""
    if period == 1:
        return datetime.date(year, month, 1), datetime.date(year, month, 15)
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, 16), datetime.date(year, month, last_day)


def get_adjacent_period(year, month, period, direction):
    """Return (year, month, period) for the previous or next pay period."""
    if direction == 'prev':
        if period == 2:
            return year, month, 1
        return (year - 1, 12, 2) if month == 1 else (year, month - 1, 2)
    else:
        if period == 1:
            return year, month, 2
        return (year + 1, 1, 1) if month == 12 else (year, month + 1, 1)


def get_bills():  # Function to get all bills
    return Entry.query.all()

@app.route('/')
def home():
    now = datetime.datetime.now()
    period = 1 if now.day <= 15 else 2
    return redirect(url_for('pay_period_view', year=now.year, month=now.month, period=period))

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

        period = 1 if due_date.day <= 15 else 2
        return redirect(url_for('pay_period_view', year=due_date.year, month=due_date.month, period=period))

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

    period = 1 if due_date.day <= 15 else 2
    return redirect(url_for('pay_period_view', year=due_date.year, month=due_date.month, period=period))

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    entry = Entry.query.get_or_404(id)  # Query for the entry with the given id

    if request.method == 'POST':
        due_date = entry.due_date
        db.session.delete(entry)  # Delete the entry from the database
        db.session.commit()  # Commit the changes to the database
        period = 1 if due_date.day <= 15 else 2
        return redirect(url_for('pay_period_view', year=due_date.year, month=due_date.month, period=period))

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

@app.route('/bill-history')
def bill_history():
    name   = request.args.get('name', '')
    year   = int(request.args.get('year',   0))
    month  = int(request.args.get('month',  0))
    period = int(request.args.get('period', 1))

    def lookup(y, m, p):
        start, end = get_pay_period_dates(y, m, p)
        entry = Entry.query.filter(
            Entry.bill_name.ilike(name),
            Entry.due_date >= start,
            Entry.due_date <= end
        ).first()
        return {
            'label':  start.strftime('%b %Y') + (' (1st–15th)' if p == 1 else ' (16th–end)'),
            'amount': entry.amount_due if entry else None,
            'url':    url_for('pay_period_view', year=y, month=m, period=p)
        }

    lm_year  = year if month > 1 else year - 1
    lm_month = month - 1 if month > 1 else 12

    return jsonify({
        'last_month': lookup(lm_year, lm_month, period),
        'last_year':  lookup(year - 1, month, period),
    })


@app.route('/settings', methods=['POST'])
def settings():
    key   = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    if key and value:
        set_config(key, value)
    return ('', 204)


@app.route('/period/<int:year>/<int:month>/<int:period>', methods=['GET', 'POST'])
def pay_period_view(year, month, period):
    start_date, end_date = get_pay_period_dates(year, month, period)

    if request.method == 'POST':
        due_date_str = request.form.get('due_date')
        bill_name = request.form.get('bill_name')
        amount_due = request.form.get('amount_due')

        if not due_date_str or not bill_name:
            return "Error: Due date and bill name are required", 400

        due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        db.session.add(Entry(due_date=due_date, bill_name=bill_name, amount_due=float(amount_due) if amount_due else 0.0))
        db.session.commit()
        return redirect(url_for('pay_period_view', year=year, month=month, period=period))

    entries = Entry.query.filter(
        Entry.due_date >= start_date,
        Entry.due_date <= end_date
    ).order_by(Entry.due_date).all()

    total_due = sum(e.amount_due for e in entries)
    prev_year, prev_month, prev_period = get_adjacent_period(year, month, period, 'prev')
    next_year, next_month, next_period = get_adjacent_period(year, month, period, 'next')

    return render_template('pay_period.html',
                           entries=entries,
                           year=year, month=month, period=period,
                           start_date=start_date, end_date=end_date,
                           total_due=total_due,
                           prev_year=prev_year, prev_month=prev_month, prev_period=prev_period,
                           next_year=next_year, next_month=next_month, next_period=next_period,
                           month_names=month_names,
                           budget_name=get_config('budget_name', 'My Budget'))
