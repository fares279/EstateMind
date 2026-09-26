"""
Management command: run_calibration_audit

Runs quarterly calibration audit to validate investment grades.
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run calibration audit for investment grades'

    def add_arguments(self, parser):
        parser.add_argument('--lookback-months', type=int, default=6)

    def handle(self, *args, **options):
        from estatemind.intelligence.investor.services.calibration_audit import CalibrationAuditService

        lookback = options['lookback_months']

        self.stdout.write(f'Running calibration audit (lookback: {lookback} months)...')

        service = CalibrationAuditService()
        result = service.run_quarterly_audit()

        if 'error' in result:
            self.stdout.write(self.style.ERROR(f'Error: {result["error"]}'))
            return

        # Pretty print results
        self.stdout.write(self.style.SUCCESS('✓ Audit completed'))
        self.stdout.write(f'  Status: {result["status"]}')
        self.stdout.write(f'  Monotonic: {result["monotonic"]}')

        if result['inversions']:
            self.stdout.write(self.style.WARNING(f'  Inversions: {", ".join(result["inversions"])}'))

        self.stdout.write('\nGrade Returns:')
        for grade, data in result['grade_returns'].items():
            self.stdout.write(
                f'  {grade}: {data["count"]:3d} properties, '
                f'mean return: {data["mean_return"]*100:+.2f}%, '
                f'std: {data["std_return"]*100:.2f}%'
            )

        self.stdout.write('\nRecommendation:')
        self.stdout.write(f'  {result["action"]}')

        self.stdout.write(self.style.SUCCESS('✓ Done'))
