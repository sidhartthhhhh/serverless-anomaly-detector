from django.core.management.base import BaseCommand

from readings.services import process_pending_readings


class Command(BaseCommand):
    help = "Run anomaly detection for readings that have not been processed yet."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        result = process_pending_readings(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {result['processed']} readings, "
                f"found {result['anomalies']} anomalies."
            )
        )
