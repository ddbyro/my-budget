from flask import Flask, jsonify, render_template, request, redirect, url_for, g
import calendar
import datetime
import os
import time
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
    """A single bill record tied to a specific due date."""
    id         = db.Column(db.Integer, primary_key=True)
    bill_name  = db.Column(db.String(80), nullable=False)
    due_date   = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)


class Config(db.Model):
    """Persistent key/value store for user-facing settings (e.g. budget_name, font_family)."""
    key   = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(200), nullable=False)


class Metric(db.Model):
    """One row per API request — used to power the /api/metrics endpoints."""
    id               = db.Column(db.Integer, primary_key=True)
    endpoint         = db.Column(db.String(120), nullable=False)
    method           = db.Column(db.String(10),  nullable=False)
    status_code      = db.Column(db.Integer,     nullable=False)
    response_time_ms = db.Column(db.Float,       nullable=False)
    timestamp        = db.Column(db.DateTime,    nullable=False,
                                 default=datetime.datetime.utcnow)


with app.app_context():
    db.create_all()


# ── Config helpers ────────────────────────────────────────────────────────────

def get_config(key, default=''):
    """Return the stored value for key, or default if the key does not exist."""
    row = Config.query.get(key)
    return row.value if row else default


def set_config(key, value):
    """Upsert a key/value pair in Config."""
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
    """Redirect to the current pay period based on today's date."""
    now = datetime.datetime.now()
    period = 1 if now.day <= 15 else 2
    return redirect(url_for('pay_period_view', year=now.year, month=now.month, period=period))


@app.route('/period/<int:year>/<int:month>/<int:period>', methods=['GET', 'POST'])
def pay_period_view(year, month, period):
    """Render the notepad page for a pay period. POST adds a new bill."""
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
    """Render the edit form for an existing bill. POST saves changes."""
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
    """Render the delete confirmation page. POST permanently removes the bill."""
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
    """Return JSON with last-month and last-year amounts for a named bill (used by the UI history popup)."""
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
    """Save a UI setting (budget_name, font_family) sent by the frontend via fetch."""
    key   = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()
    if key and value:
        set_config(key, value)
    return '', 204


# ── API metrics hooks ─────────────────────────────────────────────────────────

@app.before_request
def _api_start_timer():
    """Record request start time for API routes so response time can be calculated."""
    if request.path.startswith('/api/'):
        g.api_start = time.time()


@app.after_request
def _api_record_metric(response):
    """Persist a Metric row for every completed API request."""
    if request.path.startswith('/api/') and hasattr(g, 'api_start'):
        elapsed = round((time.time() - g.api_start) * 1000, 2)
        try:
            db.session.add(Metric(
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=elapsed,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
    return response


# ── API helpers ───────────────────────────────────────────────────────────────

def entry_to_dict(e):
    """Serialize an Entry to a JSON-safe dict."""
    return {
        'id':         e.id,
        'bill_name':  e.bill_name,
        'due_date':   e.due_date.isoformat(),
        'amount_due': e.amount_due,
    }


def api_error(msg, code=400):
    """Return a JSON error response with the given message and HTTP status code."""
    return jsonify({'error': msg}), code


# ── API: entries ──────────────────────────────────────────────────────────────

@app.route('/api/entries', methods=['GET'])
def api_entries_list():
    """List entries. Optional filters: year+month+period  OR  from+to (YYYY-MM-DD)."""
    q = Entry.query

    year   = request.args.get('year',   type=int)
    month  = request.args.get('month',  type=int)
    period = request.args.get('period', type=int)
    from_  = request.args.get('from')
    to_    = request.args.get('to')

    if year and month and period:
        start, end = get_pay_period_dates(year, month, period)
        q = q.filter(Entry.due_date >= start, Entry.due_date <= end)
    elif from_ or to_:
        if from_:
            q = q.filter(Entry.due_date >= datetime.date.fromisoformat(from_))
        if to_:
            q = q.filter(Entry.due_date <= datetime.date.fromisoformat(to_))

    entries = q.order_by(Entry.due_date).all()
    return jsonify([entry_to_dict(e) for e in entries])


@app.route('/api/entries', methods=['POST'])
def api_entries_create():
    """Create a new entry. Body: {bill_name, due_date, amount_due?}"""
    data = request.get_json(silent=True) or {}

    bill_name    = (data.get('bill_name') or '').strip()
    due_date_str = (data.get('due_date')  or '').strip()
    amount_due   = data.get('amount_due', 0.0)

    if not bill_name or not due_date_str:
        return api_error('bill_name and due_date are required')

    try:
        due_date = datetime.date.fromisoformat(due_date_str)
    except ValueError:
        return api_error('due_date must be YYYY-MM-DD')

    entry = Entry(bill_name=bill_name, due_date=due_date,
                  amount_due=float(amount_due) if amount_due else 0.0)
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry_to_dict(entry)), 201


@app.route('/api/entries/<int:entry_id>', methods=['GET'])
def api_entry_get(entry_id):
    """Return a single entry by ID."""
    entry = Entry.query.get_or_404(entry_id)
    return jsonify(entry_to_dict(entry))


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def api_entry_update(entry_id):
    """Update an entry. Body: {bill_name?, due_date?, amount_due?}"""
    entry = Entry.query.get_or_404(entry_id)
    data  = request.get_json(silent=True) or {}

    if 'bill_name' in data:
        bill_name = data['bill_name'].strip()
        if not bill_name:
            return api_error('bill_name cannot be empty')
        entry.bill_name = bill_name

    if 'due_date' in data:
        try:
            entry.due_date = datetime.date.fromisoformat(data['due_date'])
        except ValueError:
            return api_error('due_date must be YYYY-MM-DD')

    if 'amount_due' in data:
        entry.amount_due = float(data['amount_due'])

    db.session.commit()
    return jsonify(entry_to_dict(entry))


@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def api_entry_delete(entry_id):
    """Delete an entry by ID. Returns 204 No Content on success."""
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return '', 204


# ── API: pay periods ──────────────────────────────────────────────────────────

@app.route('/api/periods/<int:year>/<int:month>/<int:period>', methods=['GET'])
def api_period_summary(year, month, period):
    """Return all entries for a pay period plus totals and adjacent period links."""
    if period not in (1, 2):
        return api_error('period must be 1 or 2')

    start, end = get_pay_period_dates(year, month, period)
    entries = Entry.query.filter(
        Entry.due_date >= start,
        Entry.due_date <= end
    ).order_by(Entry.due_date).all()

    py, pm, pp = get_adjacent_period(year, month, period, 'prev')
    ny, nm, np = get_adjacent_period(year, month, period, 'next')

    return jsonify({
        'year': year, 'month': month, 'period': period,
        'start_date': start.isoformat(),
        'end_date':   end.isoformat(),
        'total_due':  round(sum(e.amount_due for e in entries), 2),
        'entries':    [entry_to_dict(e) for e in entries],
        'prev': {'year': py, 'month': pm, 'period': pp},
        'next': {'year': ny, 'month': nm, 'period': np},
    })


# ── API: settings ─────────────────────────────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def api_settings_list():
    """Return all stored settings as a {key: value} dict."""
    rows = Config.query.all()
    return jsonify({r.key: r.value for r in rows})


@app.route('/api/settings/<key>', methods=['GET'])
def api_setting_get(key):
    """Return a single setting by key. 404 if not found."""
    row = Config.query.get(key)
    if not row:
        return api_error(f'setting "{key}" not found', 404)
    return jsonify({'key': row.key, 'value': row.value})


@app.route('/api/settings/<key>', methods=['PUT'])
def api_setting_set(key):
    """Update a setting. Body: {value}"""
    data  = request.get_json(silent=True) or {}
    value = str(data.get('value', '')).strip()
    if not value:
        return api_error('value is required')
    set_config(key, value)
    return jsonify({'key': key, 'value': value})


# ── API: metrics ──────────────────────────────────────────────────────────────

@app.route('/api/metrics', methods=['GET'])
def api_metrics_list():
    """Recent API calls. Query params: limit (default 100), offset (default 0)."""
    limit  = request.args.get('limit',  100, type=int)
    offset = request.args.get('offset', 0,   type=int)

    rows = (Metric.query
            .order_by(Metric.timestamp.desc())
            .offset(offset).limit(limit).all())

    return jsonify([{
        'id':               r.id,
        'endpoint':         r.endpoint,
        'method':           r.method,
        'status_code':      r.status_code,
        'response_time_ms': r.response_time_ms,
        'timestamp':        r.timestamp.isoformat() + 'Z',
    } for r in rows])


@app.route('/api/metrics/summary', methods=['GET'])
def api_metrics_summary():
    """Aggregated stats per endpoint+method."""
    from sqlalchemy import func

    rows = (db.session.query(
                Metric.endpoint,
                Metric.method,
                func.count().label('calls'),
                func.avg(Metric.response_time_ms).label('avg_ms'),
                func.min(Metric.response_time_ms).label('min_ms'),
                func.max(Metric.response_time_ms).label('max_ms'),
                func.min(Metric.timestamp).label('first_call'),
                func.max(Metric.timestamp).label('last_call'),
            )
            .group_by(Metric.endpoint, Metric.method)
            .order_by(func.count().desc())
            .all())

    return jsonify([{
        'endpoint':   r.endpoint,
        'method':     r.method,
        'calls':      r.calls,
        'avg_ms':     round(r.avg_ms, 2),
        'min_ms':     r.min_ms,
        'max_ms':     r.max_ms,
        'first_call': r.first_call.isoformat() + 'Z',
        'last_call':  r.last_call.isoformat()  + 'Z',
    } for r in rows])
