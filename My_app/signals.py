# My_app/signals.py
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Wallet, Profile, Transaction  # ADD Transaction here!


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a Profile whenever a new User is created"""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the Profile whenever the User is saved"""
    try:
        instance.profile.save()
    except:
        # If profile doesn't exist, create it
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        # Create wallet for new user
        Wallet.objects.create(user=instance)
        # Create profile if not exists
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Transaction)  # Now Transaction is imported!
def update_wallet_on_transaction(sender, instance, created, **kwargs):
    """Update wallet balance when transaction is completed"""
    if instance.status == "COMPLETED" and created:
        try:
            wallet = instance.user.wallet

            if instance.txn_type == "DEPOSIT":
                wallet.balance += instance.amount
            elif instance.txn_type == "WITHDRAW":
                wallet.balance -= instance.amount
            # For transfers, the transfer() method handles it

            wallet.save()
        except Wallet.DoesNotExist:
            pass