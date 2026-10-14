"""
rate_limit.py
=============
Configures slowapi-based rate limiting for MortgageGuard AI.

Usage
-----
Call ``setup_rate_limiting(app)`` once after the FastAPI app is created.
Individual route handlers can be decorated with ``@limiter.limit("N per minute")``.
"""

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ---------------------------------------------------------------------------
# Shared limiter instance — import this in route modules when needed
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Attach the rate-limiter and its exception handler to a FastAPI application.

    Parameters
    ----------
    app:
        The FastAPI application instance created in ``main.py``.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
