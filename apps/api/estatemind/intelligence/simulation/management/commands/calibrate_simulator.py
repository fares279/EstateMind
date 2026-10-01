"""Calibrate the simulator's starting prices to real listings (engine/calibration.py)."""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Write data/simulator_calibration.json from real sale listings and print the error report."

    def handle(self, *args, **options):
        from estatemind.intelligence.simulation.engine.calibration import CALIBRATION_PATH, calibrate_and_save

        calibration = calibrate_and_save()
        self.stdout.write(json.dumps(calibration['report'], indent=1))
        self.stdout.write(self.style.SUCCESS(f'{len(calibration["zones"])} zones written to {CALIBRATION_PATH}'))
