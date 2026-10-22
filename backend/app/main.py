"""
main.py
=======
mortgage_assistant — Evidence-Grounded Mortgage Loan Compliance and Regulatory Intelligence Platform
FastAPI Application Entrypoint
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from backend.app.core.config import settings
from backend.app.db.session import init_db
from backend.app.middleware.rate_limit import setup_rate_limiting
from backend.app.api.routes import (
    health,
    sources,
    regulations,
    documents,
    compliance,
    reviews,
    audit,
    hmda,
    reports,
    auth,
    datasets,
    qa,
    jobs,
    retrieval,
    admin,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mortgage_assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs startup logic before yield, teardown after."""
    logger.info("Initializing mortgage_assistant database schema...")
    init_db()
    logger.info("Database schema initialized successfully.")
    yield
    # Teardown (if needed in future) goes here


app = FastAPI(
    title="morgage-loan-automation",
    description=(
        "Evidence-Grounded Mortgage Loan Compliance and Regulatory Intelligence Engine. "
        "Provides dataset-agnostic ingestion, dual-jurisdiction (CFPB US Reg Z & RBI India) compliance checking, "
        "deterministic rule verification, hybrid retrieval, structured Q&A, and n8n orchestration."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (slowapi)
setup_rate_limiting(app)

# Mount API Routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(regulations.router, prefix="/api")
app.include_router(retrieval.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(hmda.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(qa.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
def root():
    return {
        "service": "morgage-loan-automation",
        "description": "Evidence-Grounded Mortgage Loan Compliance and Regulatory Intelligence Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "jurisdictions": ["US (CFPB Regulation Z)", "IN (Reserve Bank of India)"],
        "orchestration": "n8n automation enabled",
        "disclaimer": (
            "morgage-loan-automation is a decision-support platform and does not constitute formal legal advice. "
            "Absence of an identified violation does not prove regulatory compliance."
        ),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred during compliance processing.", "error": str(exc)},
    )

