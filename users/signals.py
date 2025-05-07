from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from users.models import ReferralRewardTransaction, Wallet
from bookings.models import BusBooking, PackageBooking
from decimal import Decimal
import logging


REFERRED_REWARD = Decimal('150.00')

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=BusBooking)
def handle_bus_trip_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.trip_status != instance.trip_status:
        try:
            reward = ReferralRewardTransaction.objects.get(
                booking_type='bus',
                booking_id=instance.pk
            )
        except ReferralRewardTransaction.DoesNotExist:
            return

        referred_wallet, _ = Wallet.objects.get_or_create(user=reward.referrer)
        
        referrer_wallet, _ = Wallet.objects.get_or_create(user=reward.referred_user)

        if instance.trip_status == 'completed':
            if reward.status != 'credited':
                referrer_wallet.balance += reward.reward_amount
                referrer_wallet.referral_used = True
                referrer_wallet.save()
                
                referred_wallet.balance += REFERRED_REWARD
                referred_wallet.save()

                logger.info(f"Added {reward.reward_amount} to referrer {reward.referrer.id} wallet and {REFERRED_REWARD} to referred person {reward.referred_user.id} wallet")

                reward.status = 'credited'
                reward.credited_at = timezone.now()
                reward.save()

        elif instance.trip_status == 'cancelled':
            reward.status = 'cancelled'
            reward.save()

            referrer_wallet.referral_used = False
            referrer_wallet.save()

@receiver(pre_save, sender=PackageBooking)
def handle_package_trip_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.trip_status != instance.trip_status:
        try:
            reward = ReferralRewardTransaction.objects.get(
                booking_type='package',
                booking_id=instance.pk
            )
        except ReferralRewardTransaction.DoesNotExist:
            return

        referred_wallet, _ = Wallet.objects.get_or_create(user=reward.referrer)
        
        referrer_wallet, _ = Wallet.objects.get_or_create(user=reward.referred_user)

        if instance.trip_status == 'completed':
            if reward.status != 'credited':
                referrer_wallet.balance += reward.reward_amount
                referrer_wallet.referral_used = True
                referrer_wallet.save()
                
                referred_wallet.balance += REFERRED_REWARD
                referred_wallet.save()

                logger.info(f"Added {reward.reward_amount} to referrer {reward.referrer.id} wallet and {REFERRED_REWARD} to referred person {reward.referred_user.id} wallet")

                reward.status = 'credited'
                reward.credited_at = timezone.now()
                reward.save()

        elif instance.trip_status == 'cancelled':
            reward.status = 'cancelled'
            reward.save()

            referrer_wallet.referral_used = False
            referrer_wallet.save()