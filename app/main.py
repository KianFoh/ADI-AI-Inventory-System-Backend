from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from app.routers import users, transaction, storage_section, rfid_tags, partition, large_item, item, container
from app.security import verify_api_key

# Create FastAPI app
app = FastAPI(
    title="ADI AI Inventory System",
    description="Inventory Management System API",
    version="1.0.0"
)

# Global handler for Pydantic validation errors
@app.exception_handler(RequestValidationError)
async def fastapi_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"]
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 