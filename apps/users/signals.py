from allauth.account.models import EmailAddress
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .services.services import create_user_profile, enforce_unique_email_type_per_user


def create_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw", False):
        create_user_profile(user=instance)


@receiver(pre_save, sender=EmailAddress)
def enforce_email_address_validation_rules(sender, instance, **kwargs):
    enforce_unique_email_type_per_user(instance)
