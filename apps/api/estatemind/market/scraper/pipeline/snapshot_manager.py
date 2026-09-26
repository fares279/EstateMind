from datetime import datetime
from typing import List, Dict
from django.utils import timezone

from estatemind.market.core.models import DelegationMarketSnapshot, Delegation


class SnapshotManager:
    """Create immutable delegation market snapshots."""

    def create_snapshot(self, delegation_analytics: List[Dict]) -> str:
        snapshot_id = f"market_snapshot_{timezone.now().strftime('%Y_%m_%d_%H_%M')}"

        for delegation_data in delegation_analytics:
            # Lookup delegation instance
            delegation_obj = Delegation.objects.filter(name__iexact=delegation_data.get('delegation')).first()
            if not delegation_obj:
                continue

            DelegationMarketSnapshot.objects.create(
                delegation=delegation_obj,
                as_of_date=delegation_data.get('as_of_date') or datetime.utcnow().date(),
                listing_count=delegation_data.get('listing_count', 0),
                median_sale_price=delegation_data.get('median_sale_price'),
                median_price_per_sqm=delegation_data.get('median_price_per_sqm'),
                price_per_sqm_distribution=delegation_data.get('price_per_sqm_distribution', {}),
            )

        return snapshot_id

    def list_snapshots(self):
        return (
            DelegationMarketSnapshot.objects.values_list('as_of_date', flat=True)
            .distinct()
            .order_by('-as_of_date')
        )
