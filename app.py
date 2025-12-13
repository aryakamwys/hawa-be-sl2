"""
Vercel entrypoint for FastAPI application
This file is required by Vercel to find the FastAPI app instance
"""
from app.main import app

__all__ = ["app"]
