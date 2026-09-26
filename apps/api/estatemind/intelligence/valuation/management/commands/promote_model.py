from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from estatemind.intelligence.valuation.models import ValuationModelVersion
from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry
from estatemind.intelligence.valuation.services.promotion import ValuationPromotionGate


class Command(BaseCommand):
    help = 'Promote a valuation model version to challenger or champion.'

    def add_arguments(self, parser):
        parser.add_argument('--version-id', type=int, required=True, help='Primary key of the valuation model version')
        parser.add_argument(
            '--to',
            choices=['challenger', 'champion'],
            default='champion',
            help='Target status for the version',
        )
        parser.add_argument(
            '--traffic',
            type=int,
            default=100,
            help='Traffic allocation percentage when promoting to challenger',
        )

    def handle(self, *args, **options):
        version_id = options['version_id']
        target = options['to']
        traffic = max(1, min(100, int(options['traffic'])))

        try:
            version = ValuationModelVersion.objects.get(pk=version_id)
        except ValuationModelVersion.DoesNotExist as exc:
            raise CommandError(f'Model version {version_id} not found') from exc

        registry = ValuationModelRegistry()

        if target == 'challenger':
            version.status = 'challenger'
            version.ab_traffic_pct = traffic
            version.save(update_fields=['status', 'ab_traffic_pct', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(
                f'Version {version.id} is now a challenger with {traffic}% traffic.'
            ))
            return

        active_champion = (
            registry.list_versions(version.model_name)
            .filter(status='champion')
            .exclude(pk=version.pk)
            .first()
        )
        handle = registry._version_to_handle(version)
        model = registry._artifact_registry.maybe_load_estimator(handle)
        if model is None:
            raise CommandError('Unable to load the model artifact for promotion')

        gate = ValuationPromotionGate()
        gate_result = gate.run(version=version, model=model, champion=active_champion)
        if not gate_result.get('promoted'):
            raise CommandError(
                f"Promotion blocked: {gate_result.get('reason', 'gate failed')}"
            )

        promoted = registry.promote(version.id, promoted_by='management_command')
        self.stdout.write(self.style.SUCCESS(
            f'Version {promoted.id} promoted to champion.'
        ))
