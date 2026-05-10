import logging
import os
import sys
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger('scraper')

_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


def _auto_scrape_loop():
    """
    Background daemon: run all active scrapers followed by the full
    Bronze→Silver→Gold pipeline every 24 hours.

    Starts after a 60-second warm-up so Django is fully ready before
    the first DB access.
    """
    from django.db import connection

    time.sleep(60)  # let the server finish starting up

    while True:
        try:
            logger.info('[AutoScraper] Starting scheduled 24h scrape run')
            from django.core.management import call_command
            call_command('run_scrapers')
            call_command('process_pipeline')
            logger.info('[AutoScraper] Scheduled run complete — next run in 24 hours')
        except Exception as exc:
            logger.error('[AutoScraper] Error during scheduled run: %s', exc)
        finally:
            try:
                connection.close()
            except Exception:
                pass

        time.sleep(_INTERVAL_SECONDS)


class ScraperConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scraper'
    verbose_name = 'Real-Time Scraping & Data Collection'

    def ready(self):
        # Start the background scheduler only when the actual server process is
        # running — not during migrations, shell, or the Django reloader watcher.
        # RUN_MAIN=true is set by Django's reloader on the real server child process.
        is_server_process = (
            os.environ.get('RUN_MAIN') == 'true'
            or any('gunicorn' in a for a in sys.argv)
            or any('uvicorn' in a for a in sys.argv)
        )
        if is_server_process:
            t = threading.Thread(
                target=_auto_scrape_loop,
                name='AutoScraper-24h',
                daemon=True,
            )
            t.start()
            logger.info('[AutoScraper] Background scheduler started — interval: 24 hours')
