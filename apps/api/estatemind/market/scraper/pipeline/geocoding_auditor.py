from datetime import datetime, timezone
from typing import Dict

from estatemind.market.core.models import Property


def compute_geocoding_quality_report() -> Dict[str, object]:
    total = Property.objects.count()
    if total == 0:
        return {
            "total": 0,
            "polygon_pct": 0.0,
            "centroid_pct": 0.0,
            "missing_pct": 0.0,
            "quality_ceiling": 0.0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    polygon_count = Property.objects.filter(geocoding_precision='polygon').count()
    centroid_count = Property.objects.filter(geocoding_precision='centroid').count()
    missing_count = Property.objects.filter(geocoding_precision__isnull=True).count()

    return {
        "total": total,
        "polygon_pct": round(polygon_count / total * 100, 1),
        "centroid_pct": round(centroid_count / total * 100, 1),
        "missing_pct": round(missing_count / total * 100, 1),
        "quality_ceiling": round(polygon_count / total * 100, 1),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
