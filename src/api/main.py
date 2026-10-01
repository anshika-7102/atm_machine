"""
FastAPI Main Application Entry Point.
ATM Cash Demand Predictor & Optimization Engine.

Provides interactive Swagger UI at /docs and ReDoc at /redoc.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import router

app = FastAPI(
    title="ATM Cash Demand Predictor API",
    description=(
        "Production-grade REST API for ATM Cash Demand Forecasting, "
        "Cash-Out Risk Assessment, and CIT Replenishment Optimization. "
        "Powered by Tuned XGBoost Regressors on Tinkoff Financial Data."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Configuration - enables frontend dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local development / dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(router)

from fastapi.responses import RedirectResponse

# Mount React Frontend SPA at /dashboard and /assets if built
dist_dir = Path("frontend/dist")
if dist_dir.exists():
    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")
    app.mount("/dashboard", StaticFiles(directory=str(dist_dir), html=True), name="dashboard")


@app.get("/", tags=["System"])
async def root():
    """Redirect root directly to the React Dashboard."""
    if dist_dir.exists():
        return RedirectResponse(url="/dashboard/")
    return {
        "system": "ATM Cash Demand Predictor API",
        "status": "online",
        "version": "1.0.0",
        "dashboard_ui": "/dashboard/",
        "documentation": "/docs",
        "health_check": "/health",
        "api_v1_prefix": "/api/v1",
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for container orchestrators and monitoring tools."""
    return {
        "status": "healthy",
        "service": "atm-demand-predictor",
        "model_loaded": True,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
