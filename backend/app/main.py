from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Import routers
from app.api.routers import organizations, users, leads, lead_lists, campaigns, research, auth, webhooks, generation, sourcing

from contextlib import asynccontextmanager
import asyncio
from app.worker import autonomous_agent_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the autonomous background agent
    task = asyncio.create_task(autonomous_agent_loop())
    yield
    # Cleanup task on shutdown
    task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(lead_lists.router, prefix="/api/v1")
app.include_router(campaigns.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(generation.router, prefix="/api/v1")
app.include_router(sourcing.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}
