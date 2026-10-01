from estatemind.intelligence.climate.services.composite_scorer import score_fields
from django.core.management.base import BaseCommand
from django.utils import timezone
from estatemind.market.core.models import Delegation, DelegationClimateScore
from estatemind.intelligence.climate.services import ClimateCompositeScorer
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seeds initial climate scores for all delegations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recomputation even if scores already exist',
        )
        parser.add_argument(
            '--delegations',
            type=str,
            default='all',
            help='Comma-separated list of delegation names, or "all"',
        )
    
    def handle(self, *args, **options):
        force = options['force']
        delegations_arg = options['delegations']
        
        # Determine which delegations to process
        if delegations_arg.lower() == 'all':
            delegations = Delegation.objects.all()
            self.stdout.write(f'Processing all {delegations.count()} delegations...')
        else:
            delegation_names = [d.strip() for d in delegations_arg.split(',')]
            delegations = Delegation.objects.filter(name__in=delegation_names)
            self.stdout.write(f'Processing {delegations.count()} specified delegations...')
        
        scorer = ClimateCompositeScorer()
        processed = 0
        created = 0
        updated = 0
        errors = 0
        
        for delegation in delegations:
            try:
                # Skip if exists and not force
                if not force:
                    existing = DelegationClimateScore.objects.filter(
                        delegation=delegation
                    ).exists()
                    if existing:
                        self.stdout.write(
                            f'  ⊘ {delegation.name}: score already exists (use --force to override)'
                        )
                        processed += 1
                        continue
                
                # Compute score
                score_data = scorer.compute(delegation)
                
                # Save or update
                obj, created_flag = DelegationClimateScore.objects.update_or_create(
                    delegation=delegation,
                    defaults=score_fields(score_data)
                )
                
                action = 'CREATED' if created_flag else 'UPDATED'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ {delegation.name}: {action} '
                        f'score={score_data["composite_score"]:.3f}, '
                        f'label={score_data["risk_label"]}'
                    )
                )
                
                processed += 1
                if created_flag:
                    created += 1
                else:
                    updated += 1
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ {delegation.name}: {str(e)}')
                )
                logger.error(f'Error seeding climate score for {delegation.name}: {e}')
                errors += 1
        
        # Build kriging surface after all scores seeded
        self.stdout.write('\nBuilding kriging surface...')
        from estatemind.intelligence.climate.services import KrigingClimateService
        kriging = KrigingClimateService.get_instance()
        kriging.invalidate()
        surface_success = kriging.build_surface()
        
        if surface_success:
            report = kriging.get_surface_quality_report()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Kriging surface built: '
                    f'{report["delegation_count"]}/{report.get("coverage_pct", 0):.1f}% coverage'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('Kriging surface build failed (may be retried on next recalibration)')
            )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Climate score seeding complete!'))
        self.stdout.write(f'Processed: {processed}')
        self.stdout.write(f'Created: {created}')
        self.stdout.write(f'Updated: {updated}')
        if errors:
            self.stdout.write(self.style.WARNING(f'Errors: {errors}'))
