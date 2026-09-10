"""
Checklist generation and re-sync (plan §4.3).

Generation snapshots a requirement set. Re-sync is deliberately a separate,
explicit, staff-triggered action that reports what it changed — never an
automatic consequence of an admin editing a school's requirements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.schools.models import RequirementItem, SchoolRequirementSet

from .models import Application, ChecklistInstance, ChecklistItemInstance, StudentDocument

logger = logging.getLogger(__name__)


@dataclass
class ResyncReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not (self.added or self.removed or self.updated)

    def as_dict(self) -> dict:
        return {
            "added": self.added,
            "removed": self.removed,
            "updated": self.updated,
            "preserved": self.preserved,
        }


def resolve_requirement_set(application: Application) -> SchoolRequirementSet | None:
    """Programme-specific requirements win over the school-wide set."""
    published = SchoolRequirementSet.Status.PUBLISHED
    if application.programme_id:
        programme_set = (
            SchoolRequirementSet.objects.filter(programme=application.programme, status=published)
            .order_by("-version")
            .first()
        )
        if programme_set:
            return programme_set
    return (
        SchoolRequirementSet.objects.filter(
            school=application.school, programme__isnull=True, status=published
        )
        .order_by("-version")
        .first()
    )


def _due_date_for(item: RequirementItem, application: Application):
    from datetime import timedelta

    if item.due_offset_days is None:
        return None
    anchor = application.target_submission_date or (
        application.programme.application_deadline if application.programme_id else None
    )
    return anchor + timedelta(days=item.due_offset_days) if anchor else None


def _snapshot_fields(item: RequirementItem, application: Application) -> dict:
    """Copy a requirement definition into the fields of a checklist line."""
    return {
        "source_requirement_item": item,
        "label": item.label,
        "description": item.description,
        "help_text": item.help_text,
        "category_name": item.category.name,
        "category_slug": item.category.slug,
        "category_order": item.category.display_order,
        "is_required": item.is_required,
        "priority": item.priority,
        "evidence_type": item.evidence_type,
        "accepted_file_types": item.accepted_file_types,
        "max_file_size_mb": item.max_file_size_mb,
        "allow_multiple_files": item.allow_multiple_files,
        "shareable_key": item.shareable_key,
        "expires_after_months": item.expires_after_months,
        "display_order": item.display_order,
        "due_date": _due_date_for(item, application),
    }


@transaction.atomic
def generate_checklist(
    application: Application,
    *,
    requirement_set: SchoolRequirementSet | None = None,
    user=None,
    reuse_documents: bool = True,
) -> ChecklistInstance:
    """Create the checklist for an application by snapshotting a requirement set."""
    if hasattr(application, "checklist"):
        raise ValidationError("This application already has a checklist. Use resync_checklist().")

    requirement_set = requirement_set or resolve_requirement_set(application)
    if requirement_set is None:
        raise ValidationError(
            f"{application.school.name} has no published requirement set. "
            "Publish one before generating a checklist."
        )

    checklist = ChecklistInstance.objects.create(
        application=application,
        source_requirement_set=requirement_set,
        source_version=requirement_set.version,
    )

    items = requirement_set.items.filter(is_active=True).select_related("category")
    ChecklistItemInstance.objects.bulk_create(
        [
            ChecklistItemInstance(checklist=checklist, **_snapshot_fields(item, application))
            for item in items
        ]
    )

    if reuse_documents:
        attach_shareable_documents(checklist)

    checklist.recalculate()
    audit.record(
        "create",
        target=checklist,
        actor=user,
        metadata={
            "application_id": str(application.pk),
            "requirement_set": str(requirement_set.pk),
            "version": requirement_set.version,
            "items": len(items),
        },
        target_label=f"Checklist for {application}",
    )
    return checklist


def attach_shareable_documents(checklist: ChecklistInstance) -> int:
    """Pre-fill items the student has already satisfied elsewhere.

    A passport verified for the Sheffield application should not be demanded
    again for Leeds. Only *verified* documents auto-attach — a pending or
    rejected upload carries no assurance and gets reviewed per application.
    """
    from .models import DocumentUpload

    student_id = checklist.application.student_id
    keys = set(
        checklist.items.exclude(shareable_key="").values_list("shareable_key", flat=True)
    )
    if not keys:
        return 0

    documents = {
        doc.shareable_key: doc
        for doc in StudentDocument.objects.filter(
            student_id=student_id, shareable_key__in=keys, archived_at__isnull=True
        )
        .select_related("current_upload")
        .order_by("shareable_key", "-updated_at")
        if doc.current_upload and doc.current_upload.status == DocumentUpload.Status.VERIFIED
        and not doc.is_expired
    }
    if not documents:
        return 0

    attached = 0
    for item in checklist.items.filter(shareable_key__in=documents, document__isnull=True):
        item.document = documents[item.shareable_key]
        item.status = ChecklistItemInstance.Status.VERIFIED
        item.reviewed_at = timezone.now()
        item.save(update_fields=["document", "status", "reviewed_at", "updated_at"])
        attached += 1
    return attached


@transaction.atomic
def resync_checklist(
    checklist: ChecklistInstance,
    *,
    user=None,
    requirement_set: SchoolRequirementSet | None = None,
    remove_obsolete: bool = False,
) -> ResyncReport:
    """
    Bring a checklist up to a newer requirement set version — explicitly.

    Work already done is never destroyed:
      * items still required keep their status, document and review history;
      * genuinely new requirements are added as not-started;
      * requirements that disappeared are deactivated (or, if they already hold
        a document, left visible and reported as preserved) rather than deleted.

    ``remove_obsolete`` only ever *deactivates* — nothing is hard-deleted, so a
    mistaken re-sync is recoverable.
    """
    application = checklist.application
    requirement_set = requirement_set or resolve_requirement_set(application)
    if requirement_set is None:
        raise ValidationError("No published requirement set to re-sync against.")

    report = ResyncReport()
    live_items: dict = {}
    # Items whose source requirement was deleted outright. They still matter:
    # a student may have already satisfied one, and it must not silently vanish.
    orphans: dict[str, ChecklistItemInstance] = {}
    for item in checklist.items.all():
        if item.source_requirement_item_id:
            live_items[item.source_requirement_item_id] = item
        else:
            orphans[item.label] = item

    new_items = list(requirement_set.items.filter(is_active=True).select_related("category"))
    new_ids = {item.pk for item in new_items}

    for item in new_items:
        existing = live_items.get(item.pk)
        if existing is None:
            # A requirement removed and re-added keeps its old line (and the
            # student's work) rather than appearing as brand new.
            existing = orphans.pop(item.label, None)
        if existing is None:
            ChecklistItemInstance.objects.create(
                checklist=checklist, **_snapshot_fields(item, application)
            )
            report.added.append(item.label)
            continue

        snapshot = _snapshot_fields(item, application)
        changed = [
            f for f, v in snapshot.items()
            if f != "source_requirement_item" and getattr(existing, f) != v
        ]
        if changed or not existing.is_active:
            for f, v in snapshot.items():
                setattr(existing, f, v)
            existing.is_active = True
            existing.save()
            report.updated.append(item.label)

    obsolete = [item for req_id, item in live_items.items() if req_id not in new_ids]
    obsolete += list(orphans.values())

    for existing in obsolete:
        if not existing.is_active:
            continue
        if existing.document_id or existing.status != ChecklistItemInstance.Status.NOT_STARTED:
            # The student already did work here — keep it visible rather than
            # making their effort vanish because a school edited its list.
            report.preserved.append(existing.label)
            continue
        if remove_obsolete:
            existing.is_active = False
            existing.save(update_fields=["is_active", "updated_at"])
            report.removed.append(existing.label)

    checklist.source_requirement_set = requirement_set
    checklist.source_version = requirement_set.version
    checklist.last_resynced_at = timezone.now()
    checklist.save(
        update_fields=["source_requirement_set", "source_version", "last_resynced_at", "updated_at"]
    )
    checklist.recalculate()

    audit.record(
        "checklist_resync",
        target=checklist,
        actor=user,
        metadata={"to_version": requirement_set.version, **report.as_dict()},
        target_label=f"Checklist for {application}",
    )
    return report


def preview_resync(checklist: ChecklistInstance, requirement_set=None) -> ResyncReport:
    """Dry run — what a re-sync *would* change. Staff see this before confirming."""
    sid = transaction.savepoint()
    try:
        report = resync_checklist(checklist, requirement_set=requirement_set, remove_obsolete=True)
    finally:
        transaction.savepoint_rollback(sid)
    return report
