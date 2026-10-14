"""
classifier.py
=============
Configurable document identification and classification engine for morgage-loan-automation.
Categorizes incoming mortgage documents into:
- RESIDENTIAL_MORTGAGE_NOTE
- LOAN_AGREEMENT
- CLOSING_DISCLOSURE
- LOAN_APPLICATION
- REGULATORY_STATUTE
- REGULATORY_CIRCULAR
- POLICY_DOCUMENT

Returns predicted category, calibrated confidence, supporting cues, model version,
and assigns 'NEEDS_REVIEW' status if confidence is below threshold.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    predicted_category: str
    confidence: float
    review_status: str  # 'CONFIRMED' or 'NEEDS_REVIEW'
    supporting_features: List[str]
    model_version: str = "classifier-rule-hybrid-v1.0"
    classification_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DocumentClassifier:
    """
    Modular, rule-and-cue-based document classifier with configurable categories
    and confidence thresholds.
    """

    CONFIDENCE_THRESHOLD = 0.65

    CATEGORY_RULES = {
        "RESIDENTIAL_MORTGAGE_NOTE": {
            "keywords": ["fixed rate note", "adjustable rate note", "promise to pay", "multistate", "fannie mae", "freddie mac", "borrower's promise"],
            "weight": 1.5,
        },
        "CLOSING_DISCLOSURE": {
            "keywords": ["closing disclosure", "loan terms", "projected payments", "costs at closing", "calculating cash to close", "closing cost details"],
            "weight": 1.4,
        },
        "LOAN_AGREEMENT": {
            "keywords": ["home loan agreement", "facility agreement", "sanction details", "between the lender and borrower", "equated monthly installment", "repayment schedule"],
            "weight": 1.3,
        },
        "LOAN_APPLICATION": {
            "keywords": ["uniform residential loan application", "form 1003", "borrower information", "employment information", "assets and liabilities"],
            "weight": 1.4,
        },
        "REGULATORY_STATUTE": {
            "keywords": ["12 cfr part", "regulation z", "truth in lending act", "statute", "qualified mortgage", "ability-to-repay"],
            "weight": 1.5,
        },
        "REGULATORY_CIRCULAR": {
            "keywords": ["reserve bank of india", "dbod.no", "rbi/2023-24", "master circular", "notification", "fair lending practice"],
            "weight": 1.5,
        },
        "POLICY_DOCUMENT": {
            "keywords": ["underwriting policy", "credit policy", "compliance manual", "operational guidelines", "internal policy"],
            "weight": 1.2,
        },
    }

    def classify(self, text: str, filename: Optional[str] = None) -> ClassificationResult:
        """Classify document text and optional filename into a recognized category."""
        text_lower = text.lower()
        fn_lower = filename.lower() if filename else ""

        scores: Dict[str, float] = {}
        matched_cues: Dict[str, List[str]] = {}

        for category, config in self.CATEGORY_RULES.items():
            score = 0.0
            cues = []
            weight = config.get("weight", 1.0)

            for kw in config["keywords"]:
                if kw in text_lower:
                    score += 1.0 * weight
                    cues.append(f"body_keyword:'{kw}'")
                if kw.replace(" ", "_") in fn_lower or kw.replace(" ", "-") in fn_lower:
                    score += 2.0 * weight
                    cues.append(f"filename_cue:'{kw}'")

            scores[category] = score
            matched_cues[category] = cues

        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        total_score = sum(scores.values())
        if total_score > 0:
            confidence = min(0.99, round(best_score / (total_score + 1.0), 3) + 0.3)
        else:
            best_category = "LOAN_AGREEMENT" if "loan" in fn_lower or "loan" in text_lower else "UNKNOWN"
            confidence = 0.40

        review_status = "CONFIRMED" if confidence >= self.CONFIDENCE_THRESHOLD else "NEEDS_REVIEW"

        return ClassificationResult(
            predicted_category=best_category,
            confidence=confidence,
            review_status=review_status,
            supporting_features=matched_cues.get(best_category, [])[:5],
        )
