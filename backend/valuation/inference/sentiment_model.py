"""Sentiment analysis inference for property descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


@dataclass
class SentimentPrediction:
    sentiment_score: float  # 0-1 scale
    sentiment_label: str  # positive, neutral, negative
    description_quality: str  # good, fair, poor
    key_phrases: list[str]
    token_count: int
    description_score: float
    status: str
    warnings: list[str]
    model_info: dict[str, Any]


class SentimentModelService:
    """Load and use pre-trained TF-IDF sentiment analysis model."""

    def __init__(self, artifacts_dir: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[3]
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else root / "frontend" / "repo_clone" / "artifacts" / "models"
        self.model_path = self.artifacts_dir / "tfidf_char_sentiment.joblib"
        
        self._model: Any | None = None

    def _load_model(self) -> Any:
        """Lazy-load joblib sentiment model."""
        if self._model is not None:
            return self._model
        
        if not self.model_path.exists():
            return None
        
        try:
            self._model = joblib.load(self.model_path)
            return self._model
        except Exception:
            return None

    def analyze_description(self, description: str) -> SentimentPrediction:
        """
        Analyze property description for sentiment and quality.
        
        Args:
            description: Property description text
            
        Returns:
            SentimentPrediction with sentiment score and quality metrics
        """
        description = str(description or "").strip()
        
        if not description:
            return SentimentPrediction(
                sentiment_score=0.5,
                sentiment_label="neutral",
                description_quality="poor",
                key_phrases=[],
                token_count=0,
                description_score=0.0,
                status="no_description",
                warnings=["empty_description"],
                model_info={"status": "no_description"},
            )
        
        model = self._load_model()
        
        if model is None:
            return SentimentPrediction(
                sentiment_score=0.5,
                sentiment_label="neutral",
                description_quality="poor",
                key_phrases=[],
                token_count=len(description.split()),
                description_score=0.0,
                status="model_unavailable",
                warnings=["sentiment_model_not_available"],
                model_info={"status": "model_unavailable"},
            )
        
        try:
            # Get sentiment prediction (assume model returns probability for positive class)
            # Model should accept text and return score in [0, 1]
            if hasattr(model, 'predict_proba'):
                # If it's a classifier with predict_proba
                proba = model.predict_proba([description])[0]
                sentiment_score = float(proba[1]) if len(proba) > 1 else 0.5
            elif hasattr(model, 'predict'):
                # If it's a regressor or has direct predict
                pred = model.predict([description])
                sentiment_score = float(pred[0]) if pred is not None else 0.5
            else:
                sentiment_score = 0.5
            
            # Normalize to [0, 1] if needed
            sentiment_score = max(0.0, min(1.0, sentiment_score))
            
            # Classify sentiment
            if sentiment_score >= 0.65:
                sentiment_label = "positive"
            elif sentiment_score >= 0.35:
                sentiment_label = "neutral"
            else:
                sentiment_label = "negative"
            
            # Quality assessment based on length and sentiment
            token_count = len(description.split())
            if token_count >= 20:
                description_quality = "good"
                quality_score = 0.9
            elif token_count >= 10:
                description_quality = "fair"
                quality_score = 0.6
            else:
                description_quality = "poor"
                quality_score = 0.3
            
            # Extract key phrases (simple heuristic: words with multiple chars)
            words = description.lower().split()
            key_phrases = [w for w in words if len(w) > 4][:5]
            
            return SentimentPrediction(
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                description_quality=description_quality,
                key_phrases=key_phrases,
                token_count=token_count,
                description_score=quality_score,
                status="success",
                warnings=[] if token_count >= 10 else ["short_description"],
                model_info={
                    "model_name": "tfidf_char_sentiment",
                    "sentiment_score": sentiment_score,
                    "token_count": token_count,
                },
            )
        except Exception as exc:
            return SentimentPrediction(
                sentiment_score=0.5,
                sentiment_label="neutral",
                description_quality="poor",
                key_phrases=[],
                token_count=len(description.split()),
                description_score=0.0,
                status="analysis_error",
                warnings=[f"sentiment_analysis_error: {str(exc)}"],
                model_info={"error": str(exc)},
            )
