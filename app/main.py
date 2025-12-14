"""FastAPI application entry point."""

import asyncio
import logging
import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routes import documents, runs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Report RAG",
    description="Production-grade agentic technical report generator",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router)
app.include_router(runs.router)

# Worker thread management
worker_thread = None
worker_stop_event = threading.Event()


def run_worker_loop():
    """Run the worker loop in a background thread."""
    from app.worker import worker_loop
    logger.info("Starting background worker thread")
    worker_loop(worker_stop_event)


@app.on_event("startup")
async def startup_event():
    """Start the background worker when the app starts."""
    global worker_thread
    logger.info("Starting application...")

    # Check if tables already exist, skip migrations if so
    from app.database import SessionLocal
    import sqlalchemy

    try:
        db = SessionLocal()
        # Check if jobs table exists (last table created in migration)
        result = db.execute(sqlalchemy.text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'jobs'"))
        table_exists = result.scalar() > 0
        db.close()

        if table_exists:
            logger.info("Database tables already exist, skipping migrations")
        else:
            # Run database migrations
            logger.info("Running database migrations...")
            from alembic import command
            from alembic.config import Config
            import os

            alembic_cfg = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Startup database check/migration error: {e}")
        logger.info("Continuing startup - assuming database is ready")

    # Now start worker in background thread
    logger.info("Starting background worker thread...")
    worker_thread = threading.Thread(target=run_worker_loop, daemon=True)
    worker_thread.start()
    logger.info("Background worker thread started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the background worker when the app shuts down."""
    global worker_thread
    logger.info("Shutting down application...")

    # Signal worker to stop
    worker_stop_event.set()

    # Wait for worker thread to finish (with timeout)
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=10)
        logger.info("Background worker thread stopped")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def serve_frontend():
        """Serve frontend HTML."""
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    @app.get("/")
    def root():
        """Root endpoint when no frontend."""
        return {
            "name": "Report RAG",
            "version": "0.1.0",
            "status": "running",
        }
