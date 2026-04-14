# my-budget

A personal bill-tracking app organized around bi-monthly pay periods (1st–15th and 16th–end of month). Built with Flask, SQLAlchemy, and SQLite. Ships as a container image and exposes a full REST API.

---

## Features

- Notepad-style UI — one page per pay period with spiral binding aesthetic
- Navigate forward/backward through pay periods; jump to today with one click
- Add, edit, and delete bills per period
- Bill name autocomplete based on past entries
- Compare any bill to the same period last month and last year
- Editable budget name (persisted in the database)
- Font picker — 20 Google Fonts across Handwritten, Sans-serif, Serif, and Monospace groups
- Full REST API for all CRUD operations and settings management
- Automatic API metrics collection (call counts, response times per endpoint)

---

## Running with Docker Compose

```bash
docker compose up -d
```

The app will be available at `http://localhost:8000`.

The `./data` directory is mounted as a volume so the SQLite database persists across restarts and image updates.

To pull the latest image and restart:

```bash
docker compose pull && docker compose up -d
```

---

## Running locally

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:8000 my-budget:app
```

---

## Building the image

```bash
docker build -f Containerfile -t my-budget .
```

---

## REST API

All API endpoints are prefixed with `/api/`. Requests and responses use JSON.

### Entries

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/entries` | List entries. Filter by `?year=&month=&period=` or `?from=&to=` (YYYY-MM-DD) |
| `POST` | `/api/entries` | Create an entry. Body: `{"bill_name", "due_date", "amount_due?"}` |
| `GET` | `/api/entries/<id>` | Get a single entry |
| `PUT` | `/api/entries/<id>` | Update an entry. Body: any subset of `bill_name`, `due_date`, `amount_due` |
| `DELETE` | `/api/entries/<id>` | Delete an entry |

**Entry object:**
```json
{
  "id": 1,
  "bill_name": "Rent",
  "due_date": "2026-04-01",
  "amount_due": 1200.00
}
```

### Pay periods

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/periods/<year>/<month>/<period>` | All entries for a period with total due and prev/next links |

`period` is `1` (1st–15th) or `2` (16th–end of month).

**Response:**
```json
{
  "year": 2026, "month": 4, "period": 1,
  "start_date": "2026-04-01",
  "end_date": "2026-04-15",
  "total_due": 1450.00,
  "entries": [...],
  "prev": {"year": 2026, "month": 3, "period": 2},
  "next": {"year": 2026, "month": 4, "period": 2}
}
```

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | All settings as `{"key": "value"}` |
| `GET` | `/api/settings/<key>` | Single setting |
| `PUT` | `/api/settings/<key>` | Update a setting. Body: `{"value": "..."}` |

Available keys: `budget_name`, `font_family`.

### Metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/metrics` | Recent API calls. Query params: `limit` (default 100), `offset` (default 0) |
| `GET` | `/api/metrics/summary` | Aggregated stats per endpoint — call count, avg/min/max response time |

**Metric object:**
```json
{
  "id": 42,
  "endpoint": "/api/entries",
  "method": "GET",
  "status_code": 200,
  "response_time_ms": 3.14,
  "timestamp": "2026-04-13T12:00:00Z"
}
```

**Summary object:**
```json
{
  "endpoint": "/api/entries",
  "method": "GET",
  "calls": 87,
  "avg_ms": 4.21,
  "min_ms": 1.8,
  "max_ms": 22.5,
  "first_call": "2026-04-01T08:00:00Z",
  "last_call": "2026-04-13T11:59:00Z"
}
```

---

## Data

The SQLite database is stored at `data/my-budget.db` relative to the project root. When running via Docker Compose, this directory is bind-mounted from the host so data survives container replacement.

## Tech stack

- [Flask](https://flask.palletsprojects.com/) — web framework
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) — ORM
- [SQLite](https://www.sqlite.org/) — database
- [Gunicorn](https://gunicorn.org/) — WSGI server
- [Google Fonts](https://fonts.google.com/) — typography