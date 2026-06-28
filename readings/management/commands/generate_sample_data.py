import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from readings.services import create_reading


class Command(BaseCommand):
    help = "Generate demo sensor readings with a few injected anomalies."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=80)
        parser.add_argument("--source", default="factory-line-a")
        parser.add_argument("--metric", default="temperature")

    def handle(self, *args, **options):
        count = options["count"]
        source = options["source"]
        metric = options["metric"]
        start = timezone.now() - timedelta(minutes=count * 5)
        anomalies = 0

        for index in range(count):
            is_spike = index in {int(count * 0.35), int(count * 0.72)}
            value = random.gauss(72, 2.4)
            if is_spike:
                value += random.choice([16, -14])
                anomalies += 1

            create_reading(
                {
                    "source": source,
                    "metric": metric,
                    "value": round(value, 2),
                    "unit": "F",
                    "recorded_at": start + timedelta(minutes=index * 5),
                    "payload": {"generated": True, "injected_anomaly": is_spike},
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {count} readings with {anomalies} injected anomalies."
            )
        )
