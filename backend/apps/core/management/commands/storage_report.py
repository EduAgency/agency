"""What is actually in the bucket, per student.

    python manage.py storage_report
    python manage.py storage_report --orphans

Answers the questions that matter for keeping object storage tidy, from the
database rather than by listing the bucket — listing is a paid operation and
the database already knows what should exist:

* how much each student is storing, and in how many objects
* which uploads have a database row but no file behind them (a failed upload
  that was recorded, or a file deleted out from under the app)
* which students have no files at all, so their prefix does not exist

There is nothing to create here. Object storage has no folders: a prefix comes
into being when the first object under it is written. See apps/core/storage.py.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from apps.accounts.models import StudentProfile
from apps.applications.models import DocumentUpload
from apps.core.storage import student_prefix


def _human(size: int) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class Command(BaseCommand):
    help = "Report stored object counts and sizes per student."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orphans",
            action="store_true",
            help="Also check every upload row for a file that is actually there. Slow: one storage call per row.",
        )
        parser.add_argument("--limit", type=int, default=25)

    def handle(self, *args, **options):
        rows = (
            DocumentUpload.objects.values("document__student_id")
            .annotate(objects=Count("id"), bytes=Sum("size_bytes"))
            .order_by("-bytes")
        )
        by_student = {row["document__student_id"]: row for row in rows}

        total_objects = sum(r["objects"] for r in by_student.values())
        total_bytes = sum(r["bytes"] or 0 for r in by_student.values())

        self.stdout.write(self.style.MIGRATE_HEADING("Stored documents by student"))
        self.stdout.write(f"{'prefix':<48} {'objects':>8} {'size':>10}")

        for student_id, row in list(by_student.items())[: options["limit"]]:
            self.stdout.write(
                f"{student_prefix(student_id):<48} {row['objects']:>8} {_human(row['bytes']):>10}"
            )

        self.stdout.write("")
        self.stdout.write(
            f"{len(by_student)} student prefix(es), {total_objects} object(s), {_human(total_bytes)}."
        )

        empty = StudentProfile.objects.exclude(pk__in=by_student.keys()).count()
        if empty:
            self.stdout.write(
                f"{empty} student(s) have uploaded nothing, so they have no prefix in the bucket."
            )

        if options["orphans"]:
            self._report_orphans()

    def _report_orphans(self):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Rows whose file is missing"))
        missing = 0
        for upload in DocumentUpload.objects.select_related("document").iterator():
            if not upload.file:
                name = "(no file recorded)"
            else:
                try:
                    if upload.file.storage.exists(upload.file.name):
                        continue
                except Exception as exc:  # noqa: BLE001 - report, never crash the audit
                    self.stdout.write(f"  ? {upload.pk}: {exc}")
                    continue
                name = upload.file.name
            missing += 1
            self.stdout.write(f"  ! {upload.pk} v{upload.version} -> {name}")

        self.stdout.write(
            self.style.SUCCESS("No missing files.")
            if not missing
            else self.style.WARNING(f"{missing} row(s) have no file behind them.")
        )
