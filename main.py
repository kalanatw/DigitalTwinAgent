"""
FastAPI and Django Integration Server
"""
import os
import sys
import django
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST
project_root = Path(__file__).parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Add the project root to Python path
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
django.setup()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.staticfiles import StaticFiles
from django.core.wsgi import get_wsgi_application
from digital_twin_app.views import fastapi_app

# Create the main FastAPI application
app = FastAPI(
    title="Digital Twin Platform",
    description="Integrated Django/FastAPI Digital Twin Assistant",
    version="1.0.0"
)

# Mount Django app at /django
django_app = get_wsgi_application()
app.mount("/django", WSGIMiddleware(django_app))

# Mount FastAPI sub-application at /api
app.mount("/api", fastapi_app)

# Mount static files if in development
if os.getenv('DEBUG', 'False').lower() == 'true':
    static_path = project_root / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/")
async def root():
    """Root endpoint that redirects to Django."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/django/")

@app.get("/health")
async def health_check():
    """Health check for the entire platform."""
    return {
        "status": "healthy",
        "services": {
            "django": "running",
            "fastapi": "running",
            "redis": "connected"  # You can add actual Redis health check here
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
