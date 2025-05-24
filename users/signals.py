from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from users.models import ReferralRewardTransaction, Wallet
from bookings.models import BusBooking, PackageBooking
from admin_panel.models import AdminCommission
from decimal import Decimal
import logging

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

        if instance.trip_status == 'completed':
            if reward.status != 'credited':
                # Credit money only to referrer
                referrer_wallet, _ = Wallet.objects.get_or_create(user=reward.referrer)
                referrer_wallet.balance += reward.reward_amount
                referrer_wallet.save()

                # Update admin commission - deduct referral amount
                try:
                    admin_commission = AdminCommission.objects.get(
                        booking_type='bus',
                        booking_id=instance.pk
                    )
                    if admin_commission.original_revenue is None:
                        admin_commission.original_revenue = admin_commission.revenue_to_admin
                    
                    admin_commission.referral_deduction = reward.reward_amount
                    admin_commission.revenue_to_admin = admin_commission.original_revenue - reward.reward_amount
                    admin_commission.save()
                    
                    logger.info(f"Deducted ₹{reward.reward_amount} from admin commission for booking {instance.pk}")
                except AdminCommission.DoesNotExist:
                    logger.error(f"Admin commission not found for bus booking {instance.pk}")

                logger.info(f"Added ₹{reward.reward_amount} to referrer {reward.referrer.id} wallet")

                reward.status = 'credited'
                reward.credited_at = timezone.now()
                reward.save()

        elif instance.trip_status == 'cancelled':
            reward.status = 'cancelled'
            reward.save()

            # Reset referral_used for the referred user's wallet
            try:
                referred_wallet = Wallet.objects.get(user=reward.referred_user)
                referred_wallet.referral_used = False
                referred_wallet.save()
            except Wallet.DoesNotExist:
                pass

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

        if instance.trip_status == 'completed':
            if reward.status != 'credited':
                # Credit money only to referrer
                referrer_wallet, _ = Wallet.objects.get_or_create(user=reward.referrer)
                referrer_wallet.balance += reward.reward_amount
                referrer_wallet.save()

                # Update admin commission - deduct referral amount
                try:
                    admin_commission = AdminCommission.objects.get(
                        booking_type='package',
                        booking_id=instance.pk
                    )
                    if admin_commission.original_revenue is None:
                        admin_commission.original_revenue = admin_commission.revenue_to_admin
                    
                    admin_commission.referral_deduction = reward.reward_amount
                    admin_commission.revenue_to_admin = admin_commission.original_revenue - reward.reward_amount
                    admin_commission.save()
                    
                    logger.info(f"Deducted ₹{reward.reward_amount} from admin commission for booking {instance.pk}")
                except AdminCommission.DoesNotExist:
                    logger.error(f"Admin commission not found for package booking {instance.pk}")

                logger.info(f"Added ₹{reward.reward_amount} to referrer {reward.referrer.id} wallet")

                reward.status = 'credited'
                reward.credited_at = timezone.now()
                reward.save()

        elif instance.trip_status == 'cancelled':
            reward.status = 'cancelled'
            reward.save()

            # Reset referral_used for the referred user's wallet
            try:
                referred_wallet = Wallet.objects.get(user=reward.referred_user)
                referred_wallet.referral_used = False
                referred_wallet.save()
            except Wallet.DoesNotExist:
                pass