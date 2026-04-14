from flask import Flask, jsonify, render_template, request, redirect, url_for
import calendar
import datetime
import os
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "data", "my-budget.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
db = SQLAlchemy(app)

month_names = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


class Entry(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    bill_name  = db.Column(db.String(80), nullable=False)
    due_date   = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)


class Config(db.Model):
    key   = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(200), nullable=False)


with app.app_context():
    db.create_all()


# ── Config helpers ────────────────────────────────────────────────────────────

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


def common_context():
    """Settings shared by every rendered page."""
    return {
        'budget_name': get_config('budget_name', 'My Budget'),
        'font_family': get_config('font_family', 'Caveat'),
    }


# ── Pay-period helpers ────────────────────────────────────────────────────────

def get_pay_period_dates(year, month, period):
    """Return (start_date, end_date). Period 1 = 1–15, period 2 = 16–end."""
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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    now = datetime.datetime.now()
    period = 1 if now.day <= 15 else 2
    return redirect(url_for('pay_period_view', year=now.year, month=now.month, period=period))


@app.route('/period/<int:year>/<int:month>/<int:period>', methods=['GET', 'POST'])
def pay_period_view(year, month, period):
    start_date, end_date = get_pay_period_dates(year, month, period)

    if request.method == 'POST':
        due_date_str = request.form.get('due_date')
        bill_name    = request.form.get('bill_name')
        amount_due   = request.form.get('amount_due')

        if not due_date_str or not bill_name:
            return "Error: Due date and bill name are required", 400

        due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        db.session.add(Entry(
            due_date=due_date,
            bill_name=bill_name,
            amount_due=float(amount_due) if amount_due else 0.0
        ))
        db.session.commit()
        return redirect(url_for('pay_period_view', year=year, month=month, period=period))

    entries = Entry.query.filter(
        Entry.due_date >= start_date,
        Entry.due_date <= end_date
    ).order_by(Entry.due_date).all()

    total_due = sum(e.amount_due for e in entries)
    prev_year, prev_month, prev_period = get_adjacent_period(year, month, period, 'prev')
    next_year, next_month, next_period = get_adjacent_period(year, month, period, 'next')

    bill_names = [r[0] for r in db.session.query(Entry.bill_name)
                  .distinct().order_by(Entry.bill_name).all()]

    now = datetime.datetime.now()
    today_year   = now.year
    today_month  = now.month
    today_period = 1 if now.day <= 15 else 2
    is_today = (year == today_year and month == today_month and period == today_period)

    return render_template('pay_period.html',
                           entries=entries,
                           year=year, month=month, period=period,
                           start_date=start_date, end_date=end_date,
                           total_due=total_due,
                           prev_year=prev_year, prev_month=prev_month, prev_period=prev_period,
                           next_year=next_year, next_month=next_month, next_period=next_period,
                           month_names=month_names,
                           bill_names=bill_names,
                           is_today=is_today,
                           today_year=today_year,
                           today_month=today_month,
                           today_period=today_period,
                           **common_context())


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    entry = Entry.query.get_or_404(id)

    if request.method == 'POST':
        due_date_str = request.form.get('due_date')
        bill_name    = request.form.get('bill_name')
        amount_due   = request.form.get('amount_due')

        if not due_date_str or not bill_name:
            return "Error: Due date and bill name are required", 400

        due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        entry.due_date   = due_date
        entry.bill_name  = bill_name
        entry.amount_due = float(amount_due) if amount_due else 0.0
        db.session.commit()

        period = 1 if due_date.day <= 15 else 2
        return redirect(url_for('pay_period_view', year=due_date.year, month=due_date.month, period=period))

    return render_template('edit.html', entry=entry, **common_context())


@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    entry = Entry.query.get_or_404(id)

    if request.method == 'POST':
        due_date = entry.due_date
        db.session.delete(entry)
        db.session.commit()
        period = 1 if due_date.day <= 15 else 2
        return redirect(url_for('pay_period_view', year=due_date.year, month=due_date.month, period=period))

    return render_template('delete.html', entry=entry, **common_context())


@app.route('/bill-history')
def bill_history():
    name   = request.args.get('name', '')
    year   = int(request.args.get('year',   0))
    month  = int(request.args.get('month',  0))
    period = int(request.args.get('period', 1))

    def lookup(y, m, p):
        start, end = get_pay_period_dates(y, m, p)
        e = Entry.query.filter(
            Entry.bill_name.ilike(name),
            Entry.due_date >= start,
            Entry.due_date <= end
        ).first()
        return {
            'label':  start.strftime('%b %Y') + (' (1st–15th)' if p == 1 else ' (16th–end)'),
            'amount': e.amount_due if e else None,
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
    return '', 204
