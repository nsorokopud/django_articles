from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    can_import_settings = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            action="store_false",
            dest="interactive",
            default=True,
            help="Do NOT prompt the user for input of any kind.",
        )

    def handle(self, *args, **options):
        if options["interactive"]:
            confirm = input("This will overwrite any existing files. Proceed? ")
            if not confirm.lower().startswith("y"):
                raise CommandError("Media syncing aborted")

        fixture_media_dir = str(settings.BASE_DIR / "fixtures" / "media")
        for path in Path(fixture_media_dir).glob("**/*"):
            if not (path.is_file() and self.is_valid_media_file(path)):
                continue
            try:
                dest_path = str(path).split(fixture_media_dir)[-1].lstrip("/")
                if default_storage.exists(dest_path):
                    self.stderr.write(f"File '{dest_path}' already exists.\n")
                    continue
                with open(path, "rb") as file:
                    default_storage.save(dest_path, File(file))
                self.stdout.write(f"Copied {path}\n")
            except Exception as e:
                self.stderr.write(repr(e))

    def is_valid_media_file(self, file_path) -> bool:
        return str(file_path).split(".")[-1] in ["jpg", "jpeg", "png", "bmp"]
