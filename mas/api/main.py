"""FastAPI main application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mas.api.routes import router as api_router
from mas.api.websocket import ws_router
from mas.core.proxy import proxy_app
from mas.db.session import init_db

app = FastAPI(
    title="MAS — Multi-Agent Software Engineering Team API",
    version="0.1.0",
    description="Local single-user research platform for multi-agent software development.",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Mount API and WebSocket routes
app.include_router(api_router)
app.include_router(ws_router)

# Mount logging proxy under /proxy or proxy_app
app.mount("/proxy", proxy_app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mas-api", "version": "0.1.0"}
