from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AdminProfile, StudentProfile, User


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance: User, created: bool, **kwargs):
    """Every user gets exactly one profile, chosen by role.

    Kept in a signal rather than in the serializer so users created from the
    Django admin, a management command or a test factory are equally complete.
    """
    if not created:
        return
    if instance.is_student:
        StudentProfile.objects.get_or_create(user=instance)
    elif instance.is_agency_staff:
        profile, _ = AdminProfile.objects.get_or_create(user=instance)
        profile.apply_role_defaults()
