from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserWallet,ReferralTransaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction


User = get_user_model()

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        UserWallet.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_wallet(sender, instance, **kwargs):
    if not hasattr(instance, 'wallet'):
        UserWallet.objects.create(user=instance)

@receiver(post_save, sender='buses.BusBooking')
def process_bus_booking_completion(sender, instance, **kwargs):
    if instance.trip_status == 'completed':
        try:
            referral = ReferralTransaction.objects.get(
                booking_type='bus',
                booking_id=instance.id,
                status='pending'
            )
            
            with transaction.atomic():
                referral.status = 'completed'
                referral.completed_at = timezone.now()
                referral.save()
                
                wallet = UserWallet.objects.get(user=referral.user)
                wallet.balance += referral.amount
                wallet.save()
                
                from notifications.utils import send_notification
                send_notification(
                    user=referral.user,
                    message=f"You received ₹{referral.amount} in your wallet from a referral! Thank you for referring your friend."
                )
        except ReferralTransaction.DoesNotExist:
            pass

@receiver(post_save, sender='packages.PackageBooking')
def process_package_booking_completion(sender, instance, **kwargs):
    if instance.trip_status == 'completed':
        try:
            referral = ReferralTransaction.objects.get(
                booking_type='package',
                booking_id=instance.id,
                status='pending'
            )
            
            with transaction.atomic():
                referral.status = 'completed'
                referral.completed_at = timezone.now()
                referral.save()
                
                wallet = UserWallet.objects.get(user=referral.user)
                wallet.balance += referral.amount
                wallet.save()
                
                from notifications.utils import send_notification
                send_notification(
                    user=referral.user,
                    message=f"You received ₹{referral.amount} in your wallet from a referral! Thank you for referring your friend."
                )
        except ReferralTransaction.DoesNotExist:
            pass