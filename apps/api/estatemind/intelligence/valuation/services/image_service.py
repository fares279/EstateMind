"""
Image quality scoring using PIL — no ML model required.
Mirrors the source ImageQualityService heuristics.
"""
import io
import logging

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _score_one(img_file) -> dict:
    """Score a single uploaded file (Django InMemoryUploadedFile or similar)."""
    try:
        data = img_file.read()
        img_file.seek(0)
        img = PILImage.open(io.BytesIO(data)).convert('RGB')
        w, h = img.size

        # Resolution score
        res_score = min((w * h) / (1280 * 720), 1.0)

        # Brightness score
        import statistics
        pixels = list(img.getdata())
        brightness = sum(sum(p) / (3 * 255) for p in pixels) / len(pixels)
        bright_score = 1.0 - abs(brightness - 0.55) / 0.55

        combined = 0.6 * res_score + 0.4 * bright_score
        return {
            'width': w, 'height': h,
            'resolution_score': round(res_score, 3),
            'brightness_score': round(max(0, bright_score), 3),
            'quality_score':    round(combined, 3),
        }
    except Exception as exc:
        logger.debug("Image scoring failed: %s", exc)
        return {'quality_score': 0.5}


def analyze_images(image_files: list) -> dict:
    """
    Analyse a list of uploaded image files.
    Returns dict compatible with response_builder image_analysis field.
    """
    count = len(image_files)
    if count == 0:
        return {
            'image_count':    0,
            'quality_score':  0.0,
            'coverage_score': 0.0,
            'avg_resolution': None,
            'status':         'no_images',
            'image_analysis': 'No images uploaded.',
            'cv_mode':        'no_cv',
            'per_image':      [],
        }

    coverage = min(count / 4.0, 1.0)

    if not PIL_AVAILABLE:
        return {
            'image_count':    count,
            'quality_score':  0.5,
            'coverage_score': round(coverage, 2),
            'avg_resolution': None,
            'status':         'count_only',
            'image_analysis': f'{count} image(s) received. PIL unavailable for quality scoring.',
            'cv_mode':        'no_cv',
            'per_image':      [],
        }

    scores = [_score_one(f) for f in image_files]
    avg_quality = sum(s.get('quality_score', 0.5) for s in scores) / len(scores)

    return {
        'image_count':    count,
        'quality_score':  round(avg_quality, 3),
        'coverage_score': round(coverage, 2),
        'avg_resolution': None,
        'status':         'ok',
        'image_analysis': (
            f"{count} image(s) analysed. "
            f"Average quality score: {avg_quality:.0%}. "
            "Computer vision model not loaded — visual property-type classification unavailable."
        ),
        'cv_mode': 'quality_only',
        'per_image': scores,
    }
