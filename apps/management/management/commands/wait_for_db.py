import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Waits until the database is available."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=float,
            default=1,
            help="Time in seconds to wait between retries (default is 1 second).",
        )
        parser.add_argument(
            "--max-tries",
            type=int,
            default=60,
            help="Maximum number of retries before giving up (default is 60).",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        max_tries_count = options["max_tries"]

        self.stdout.write(
            f"Waiting for DB (timeout: {timeout}s, max tries: {max_tries_count})"
        )
        current_try = 1

        while current_try <= max_tries_count:
            self.stdout.write(f"Attempt {current_try}/{max_tries_count}")
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database available!"))
                break
            except OperationalError:
                time.sleep(timeout)
                current_try += 1
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Max attempts reached ({max_tries_count})."
                    " Database still unavailable!"
                )
            )
