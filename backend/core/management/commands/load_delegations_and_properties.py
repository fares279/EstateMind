from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.data_pipeline import import_market_csvs


class Command(BaseCommand):
    help = "Load delegations and properties from CSVs, normalize them, and rebuild market snapshots."

    def add_arguments(self, parser):
        parser.add_argument(
            "delegations_csv",
            nargs="?",
            help="Path to delegations CSV",
        )
        parser.add_argument(
            "properties_csv",
            nargs="?",
            help="Path to properties CSV",
        )
        parser.add_argument(
            "--skip-aggregates",
            action="store_true",
            help="Load raw data without rebuilding delegation market aggregates.",
        )

    def handle(self, *args, **options):
        # Default paths — both CSVs are now bundled inside the project under backend/data/
        backend_data_dir = Path(__file__).resolve().parents[3] / "data"

        delegations_csv = Path(
            options["delegations_csv"] or backend_data_dir / "delegations.csv"
        )
        properties_csv = Path(
            options["properties_csv"] or backend_data_dir / "properties.csv"
        )

        if not delegations_csv.exists():
            raise CommandError(f"Delegations CSV not found: {delegations_csv}")
        if not properties_csv.exists():
            raise CommandError(f"Properties CSV not found: {properties_csv}")

        stats = import_market_csvs(
            delegations_csv=delegations_csv,
            properties_csv=properties_csv,
            rebuild_aggregates=not options["skip_aggregates"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Loaded market data successfully "
                f"(regions={stats.regions_created}, delegations={stats.delegations_created}, "
                f"properties_created={stats.properties_created}, properties_updated={stats.properties_updated}, "
                f"dedupe_merged={stats.delegation_duplicates_merged}, "
                f"snapshots={stats.snapshots_built}, segments={stats.segments_built})"
            )
        )
