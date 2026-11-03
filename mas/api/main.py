import os
import sys
from contextlib import asynccontextmanager

# Ensure repository root is on sys.path so 'eval' and 'mas' are resolvable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mas.api.routes import router as api_router
from mas.api.websocket import ws_router
from mas.core.proxy import proxy_app
from mas.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MAS — Multi-Agent Software Engineering Team API",
    version="0.1.0",
    description="Local single-user research platform for multi-agent software development.",
    lifespan=lifespan,
)

# Mount API and WebSocket routes
app.include_router(api_router)
app.include_router(ws_router)

# Mount logging proxy under /proxy or proxy_app
app.mount("/proxy", proxy_app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mas-api", "version": "0.1.0"}
