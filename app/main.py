import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .db import init_db
from .services.fix_gateway import fix_gateway
# Fase 2.2 — WS router
from .ws import ws_router
# Monolito v1 stubs
from .v1.api import v1

app = FastAPI(title="OMS Backend (MVP)")

# CORS for local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Start FIX worker properly when FastAPI starts — THIS IS CRITICAL
@app.on_event("startup")
async def startup_event():
    await init_db()
    await fix_gateway.start()

# Issue #6: Clean shutdown of FIX worker task
@app.on_event("shutdown")
async def shutdown_event():
    await fix_gateway.stop()

# Add API routes
app.include_router(router)
app.include_router(ws_router)
app.include_router(v1)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
