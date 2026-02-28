# 💰 My Finance Tracker

A full-stack personal expense tracking application with receipt OCR parsing.

## Architecture

```
my-finance/
├── backend/          # FastAPI REST API + SQLite
├── receipt_parser/   # FastAPI OCR microservice (Tesseract)
├── frontend/         # Streamlit web UI
├── data/             # Persisted DB & receipt images (auto-created)
└── docker-compose.yml
```

| Service        | Port  | Description                          |
|----------------|-------|--------------------------------------|
| Backend API    | 8000  | CRUD expenses, receipt upload proxy  |
| Receipt Parser | 8001  | OCR parsing microservice             |
| Frontend UI    | 8501  | Streamlit dashboard                  |

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

Then open **http://localhost:8501** in your browser.

## Manual Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
mkdir -p data/receipts
uvicorn main:app --reload --port 8000
```

### Receipt Parser

```bash
# Requires tesseract-ocr: sudo apt install tesseract-ocr
cd receipt_parser
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Environment Variables

| Variable             | Default                  | Description                       |
|----------------------|--------------------------|-----------------------------------|
| `RECEIPT_PARSER_URL` | `http://localhost:8001`  | URL of the receipt parser service |
| `BACKEND_URL`        | `http://localhost:8000`  | URL of the backend API            |

## API Documentation

With the backend running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Method | Path                   | Description              |
|--------|------------------------|--------------------------|
| GET    | `/health`              | Health check             |
| GET    | `/expenses`            | List expenses (filterable)|
| POST   | `/expenses`            | Create expense           |
| GET    | `/expenses/{id}`       | Get expense by ID        |
| PUT    | `/expenses/{id}`       | Update expense           |
| DELETE | `/expenses/{id}`       | Delete expense           |
| POST   | `/receipts/upload`     | Upload & parse receipt   |

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```
