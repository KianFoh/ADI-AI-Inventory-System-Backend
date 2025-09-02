# Database Migration
alembic revision --autogenerate -m "Message"
alembic upgrade head

# Launch API

## Development 
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## Production
uvicorn app.main:app --host 0.0.0.0 --port 8000