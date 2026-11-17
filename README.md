# Vehicle Entry & Exit Management System

Django + Django REST Framework + PostgreSQL backend that records vehicle entries and
exits at construction sites, auto-creates vehicle master records, tracks vehicles
currently inside, and produces a daily report.

## Technologies
Python 3, Django, Django REST Framework, PostgreSQL, psycopg2, python-dotenv.

## Prerequisites
Python 3.10+, PostgreSQL 14+, Git.

## Setup
```bash
git clone <repo-url>
cd vehicle_management
python -m venv venv
venv\Scripts\activate          # Windows (Mac/Linux: source venv/bin/activate)
python -m pip install -r requirements.txt
```

## PostgreSQL
```sql
CREATE DATABASE vehicle_db;
```

## Environment variables
Copy `.env.example` to `.env` and fill in real values (never commit `.env`):
```
SECRET_KEY=...
DEBUG=True
DB_NAME=vehicle_db
DB_USER=postgres
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432      # use the port your PostgreSQL listens on
```

## Migrations, test user, run
```bash
python manage.py migrate
python manage.py createsuperuser      # this user authenticates API calls
python manage.py runserver
```

## Run tests
```bash
python manage.py test
```

## Authentication
All endpoints require authentication (Basic or Session). In Postman use
Authorization > Basic Auth with the user created above.

## Endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| POST | /api/vehicles/ | Optional manual registration |
| GET | /api/vehicles/ | List vehicles |
| GET | /api/vehicles/{id}/ | Vehicle detail |
| PUT/PATCH | /api/vehicles/{id}/ | Update vehicle |
| POST | /api/entries/ | Record entry (auto-creates vehicle) |
| POST | /api/entries/{id}/exit/ | Record exit |
| GET | /api/entries/ | History; filters: vehicle_number, status, date |
| GET | /api/entries/inside/ | Vehicles currently inside |
| GET | /api/reports/daily/?date=YYYY-MM-DD | Daily report |

## Sample requests
Entry:
```json
POST /api/entries/
{"vehicle_number": "KA03AB1234", "vehicle_type": "TRUCK", "driver_name": "Ramesh",
 "driver_mobile": "9876543210", "vendor_name": "ABC Cement Suppliers",
 "purpose": "MATERIAL_DELIVERY"}
```
Exit: `POST /api/entries/101/exit/` with body `{}`.

## Design notes
- A conditional unique constraint (one `INSIDE` row per vehicle) makes duplicate active
  entries impossible even under simultaneous requests.
- Check constraints: exit_time >= entry_time, and status always agrees with exit_time.
- Entry creation (vehicle lookup/creation + entry) is atomic; a rejected entry leaves nothing behind.
- Exit uses `select_for_update` inside a transaction.
- Clients cannot set entry_time, exit_time or status.
- Optimization: `select_related("vehicle")` on entry queries; indexes on status,
  entry_time and exit_time.
- Timezone: Asia/Kolkata with USE_TZ=True; date filters and the report use that timezone.

## Assumptions / known limitations
- Mobile numbers must be exactly 10 digits.
- A vehicle's type can only be changed through the vehicle update API.
- Validation errors from serializers are field-keyed objects, while business-rule errors
  use `{"error": "..."}`.
- No pagination, CSV export or Swagger docs (optional bonuses not attempted).