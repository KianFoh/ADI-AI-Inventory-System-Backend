from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from app.routers import users, transaction, storage_section, rfid_tags, partition, large_item, item, container, ai_vision
from app.security import verify_api_key

# Create FastAPI app
app = FastAPI(
    title="ADI AI Inventory System",
    description="Inventory Management System API",
    version="1.0.0"
)

# Global handler for Pydantic validation errors Formatting
@app.exception_handler(RequestValidationError)
async def fastapi_validation_exception_handler(request: Request, exc: RequestValidationError):
    import re
    errors = []
    for err in exc.errors():
        loc = err["loc"]
        # Remove "body" prefix if present
        if loc and loc[0] == "body":
            loc = loc[1:]
        field_name = ".".join(str(l) for l in loc)
        msg = err["msg"]
        # Remove common error prefixes using regex
        msg = re.sub(r"^(value is not a valid|Value error,|Value error|type error,|type error|none is not an allowed value|none is not allowed|not a valid)[:\s]*", "", msg, flags=re.IGNORECASE)
        # If message contains a colon, take only the part after the colon
        if ':' in msg:
            msg = msg.split(':', 1)[1].strip()
        # Replace 'input should be a valid string' with '<Field> cannot be empty'
        if msg.strip().lower() == "input should be a valid string":
            last_field = field_name.split('.')[-1] if field_name else "Field"
            msg = f"{last_field.capitalize()} cannot be empty"
        # Remove trailing punctuation and whitespace
        msg = msg.strip().rstrip('.')
        errors.append({
            "field": field_name,
            "message": msg
        })
    return JSONResponse(
        status_code=422,
        content={"detail": errors}
    )

# Protected endpoints (require Bearer token)
@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {
        "message": "ADI AI Inventory System API",
        "status": "running",
        "version": "1.0.0"
    }

# Protected routes (require Bearer token)
app.include_router(users.router, dependencies=[Depends(verify_api_key)])
app.include_router(transaction.router, dependencies=[Depends(verify_api_key)])
app.include_router(storage_section.router, dependencies=[Depends(verify_api_key)])
app.include_router(rfid_tags.router, dependencies=[Depends(verify_api_key)])
app.include_router(partition.router, dependencies=[Depends(verify_api_key)])
app.include_router(container.router, dependencies=[Depends(verify_api_key)])
app.include_router(large_item.router, dependencies=[Depends(verify_api_key)])
app.include_router(item.router, dependencies=[Depends(verify_api_key)])
app.include_router(ai_vision.router, dependencies=[Depends(verify_api_key)])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)