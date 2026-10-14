"""
test_hmda_analytics.py
======================
Tests for authentic HMDA lending analytics and compliance disclaimers.
"""

from backend.app.db.session import SessionLocal
from backend.app.services.hmda.analytics import HMDAAnalyticsService


def test_hmda_analytics_computation():
    db = SessionLocal()
    try:
        service = HMDAAnalyticsService(db)
        analytics = service.compute_analytics()

        assert analytics.total_records >= 100
        assert "CFPB/FFIEC" in analytics.sample_size_notes
        assert "Regulation C" in analytics.disclaimer
        assert "does NOT establish legal compliance" in analytics.disclaimer
        assert analytics.avg_loan_amount > 0
        assert analytics.median_loan_amount > 0
        assert len(analytics.loan_types_distribution) > 0
        assert len(analytics.actions_taken_distribution) > 0
        assert 0.0 <= analytics.approval_rate_percent <= 100.0
        assert 0.0 <= analytics.denial_rate_percent <= 100.0
    finally:
        db.close()
