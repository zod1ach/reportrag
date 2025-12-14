"""FastAPI application entry point."""

import logging
import os

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
