# 💰 My Finance Tracker

A full-stack personal expense tracking application built with **FastAPI**, **SQLite**, and **Streamlit**.

---

## Architecture

```
my-finance/
├── backend/            # FastAPI REST API + SQLite database
│   ├── main.py         # Application entry-point, middleware, router wiring
│   ├── database.py     # SQLAlchemy engine, session factory, Base class
│   ├── models.py       # ORM models: User, Expense
│   ├── schemas.py      # Pydantic request/response schemas
│   ├── routers/
│   │   ├── expenses.py # CRUD endpoints for expense records
│   │   └── receipts.py # Receipt image upload + parser proxy
│   └── tests/
│       └── test_expenses.py  # Pytest suite for all expense endpoints
├── receipt_parser/     # Lightweight FastAPI microservice for receipt parsing
│   ├── main.py         # Service entry-point, /parse_receipt endpoint
│   └── parser.py       # Stub parser – returns hardcoded sample data (swap for OCR later)
├── frontend/           # Streamlit web UI
│   └── app.py          # Dashboard, Add Expense, Upload Receipt pages
├── docker-compose.yml  # Orchestrates all three services
└── data/               # Auto-created at runtime: finance.db + receipt images
```

| Service        | Port  | Description                                              |
|----------------|-------|----------------------------------------------------------|
| Backend API    | 8000  | CRUD for expenses; receipt upload; SQLite persistence    |
| Receipt Parser | 8001  | Stub microservice; returns sample parsed receipt JSON    |
| Frontend UI    | 8501  | Streamlit dashboard (desktop & mobile browser)           |

### Request flow

```
Browser  →  Streamlit UI (:8501)
               │
               │  REST calls (httpx)
               ▼
         FastAPI Backend (:8000)
               │              │
         SQLite DB       Receipt Parser (:8001)
                              │
                         stub / future OCR
```

---

## Module documentation

### `backend/database.py`
Configures the SQLAlchemy engine pointing at `data/finance.db`.  Provides
`get_db()` — a FastAPI dependency that yields a per-request `Session` and
closes it automatically.

### `backend/models.py`
Declares two ORM tables:
- **`users`** — optional user accounts (nullable FK on expenses for now).
- **`expenses`** — each expense stores date, store name, total, an optional
  receipt image path, notes, and a JSON-encoded list of line items.  The
  `Expense.items` Python property transparently serialises/deserialises the
  JSON column.

### `backend/schemas.py`
Pydantic v2 schemas used by FastAPI for automatic request validation and
response serialisation: `ExpenseCreate`, `ExpenseUpdate`, `ExpenseResponse`,
`UserCreate`, `UserResponse`.

### `backend/routers/expenses.py`
Five endpoints under `/expenses`:
`GET /`, `POST /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`.
Supports `start_date`, `end_date`, and `store` query filters.

### `backend/routers/receipts.py`
`POST /receipts/upload` — saves the uploaded image to disk, calls the Receipt
Parser service, and creates an `Expense` record from the returned data.
Gracefully degrades if the parser service is unreachable.

### `receipt_parser/parser.py`
**Stub implementation.**  `parse_receipt_image(image_bytes)` currently ignores
the image and returns a hardcoded sample receipt so the full stack can be
exercised without OCR dependencies.  Replace this function with a real OCR
implementation (e.g. pytesseract, Google Vision API) when needed — the
returned dict shape must stay the same.

### `receipt_parser/main.py`
Thin FastAPI wrapper around `parser.parse_receipt_image`.  Exposes
`POST /parse_receipt` (multipart image) and `GET /health`.

### `frontend/app.py`
Streamlit single-file app with three pages:
- **Dashboard** — metrics, Plotly spending-by-store bar chart, filterable table.
- **Add Expense** — manual form with dynamic item list.
- **Upload Receipt** — image upload → backend → parsed data display.

---

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

Open **http://localhost:8501** in your browser (works on desktop and mobile).

---

## Manual Setup

### 1 — Backend

```bash
cd backend
pip install -r requirements.txt
mkdir -p data/receipts
uvicorn main:app --reload --port 8000
```

### 2 — Receipt Parser

```bash
cd receipt_parser
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### 3 — Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

---

## Environment Variables

| Variable             | Default                 | Description                          |
|----------------------|-------------------------|--------------------------------------|
| `RECEIPT_PARSER_URL` | `http://localhost:8001` | URL of the receipt parser service    |
| `BACKEND_URL`        | `http://localhost:8000` | URL of the backend API (frontend)    |

---

## API Documentation

With the backend running, visit:

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc**      : http://localhost:8000/redoc

### Key Endpoints

| Method | Path               | Description                          |
|--------|--------------------|--------------------------------------|
| GET    | `/health`          | Health check                         |
| GET    | `/expenses`        | List expenses (filterable)           |
| POST   | `/expenses`        | Create expense                       |
| GET    | `/expenses/{id}`   | Get expense by ID                    |
| PUT    | `/expenses/{id}`   | Update expense                       |
| DELETE | `/expenses/{id}`   | Delete expense                       |
| POST   | `/receipts/upload` | Upload receipt image → create expense|

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```
