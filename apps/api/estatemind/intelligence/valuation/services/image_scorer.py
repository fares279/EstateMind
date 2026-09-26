from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class PropertyImageScorer:
    """Lightweight image-conditioned score with optional deep-learning hook."""

    QUALITY_THRESHOLD = 0.35

    def score(self, image_paths: list[str]) -> dict:
        if not image_paths:
            return self._no_image_fallback()

        try:
            scores = []
            qualities = []
            for image_path in image_paths:
                result = self._embed_image(Path(image_path))
                if result['quality'] >= self.QUALITY_THRESHOLD:
                    scores.append(result['condition_score'])
                    qualities.append(result['quality'])
            if not scores:
                return self._low_quality_fallback(len(image_paths))
            return {
                'condition_score': round(float(np.mean(scores)), 1),
                'image_confidence': round(float(np.mean(qualities)), 2),
                'images_used': len(scores),
                'images_rejected': len(image_paths) - len(scores),
                'available': True,
            }
        except Exception as exc:
            logger.warning('Image scorer failed: %s', exc)
            return self._no_image_fallback()

    def _embed_image(self, path: Path) -> dict[str, float]:
        try:
            from PIL import Image, ImageStat

            image = Image.open(path).convert('RGB')
            stats = ImageStat.Stat(image)
            brightness = float(sum(stats.mean) / 3.0) / 255.0
            contrast = float(sum(stats.stddev) / 3.0) / 128.0
            quality = max(0.0, min(1.0, 0.25 + (0.5 * contrast) + (0.25 * (1 - abs(brightness - 0.55)))))
            condition_score = max(0.0, min(100.0, 35 + (quality * 55) + (brightness * 10)))
            return {'quality': quality, 'condition_score': condition_score}
        except Exception:
            return {'quality': 0.0, 'condition_score': 0.0}

    def _no_image_fallback(self) -> dict:
        return {
            'condition_score': None,
            'image_confidence': None,
            'images_used': 0,
            'images_rejected': 0,
            'available': False,
        }

    def _low_quality_fallback(self, rejected: int) -> dict:
        return {
            'condition_score': None,
            'image_confidence': 0.0,
            'images_used': 0,
            'images_rejected': rejected,
            'available': False,
        }
