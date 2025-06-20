from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from users.models import ReferralRewardTransaction, Wallet
from bookings.models import BusBooking, PackageBooking
from admin_panel.models import AdminCommission
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=BusBooking)
def handle_bus_trip_status_change(sender, instance, created, **kwargs):
    """
    Handle referral rewards when bus booking trip status changes
    """
    # Skip for new bookings
    if created:
        return
    
    print(f"🔥 BUS BOOKING SIGNAL TRIGGERED for booking {instance.booking_id}")
    logger.info(f"Bus booking signal triggered for booking {instance.booking_id}")
    
    # Get the current state from database to compare
    try:
        # We need to check if there's an actual status change
        # Since this is post_save, we'll rely on the current status
        current_status = instance.trip_status
        print(f"📊 Current trip status: {current_status}")
        
        # Check if there's a pending referral reward for this booking
        try:
            reward = ReferralRewardTransaction.objects.get(
                booking_type='bus',
                booking_id=instance.booking_id,  # Use booking_id instead of pk
                status='pending'
            )
            print(f"✅ Found pending reward: {reward.id} for amount ₹{reward.reward_amount}")
        except ReferralRewardTransaction.DoesNotExist:
            print(f"❌ No pending referral reward found for bus booking {instance.booking_id}")
            logger.info(f"No pending referral reward found for bus booking {instance.booking_id}")
            return
        except ReferralRewardTransaction.MultipleObjectsReturned:
            print(f"⚠️ Multiple pending rewards found for bus booking {instance.booking_id}")
            logger.warning(f"Multiple pending rewards found for bus booking {instance.booking_id}")
            reward = ReferralRewardTransaction.objects.filter(
                booking_type='bus',
                booking_id=instance.booking_id,
                status='pending'
            ).first()

        if current_status == 'completed':
            print("💰 Processing trip completion...")
            
            # Credit money to referrer
            referrer_wallet, created = Wallet.objects.get_or_create(user=reward.referrer)
            old_balance = referrer_wallet.balance
            referrer_wallet.balance += reward.reward_amount
            referrer_wallet.save()
            
            print(f"✅ Referrer wallet updated: ₹{old_balance} → ₹{referrer_wallet.balance}")

            # Update admin commission - deduct referral amount
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='bus',
                    booking_id=instance.booking_id  # Use booking_id instead of pk
                )
                
                # Store original revenue if not already stored
                if admin_commission.original_revenue is None:
                    admin_commission.original_revenue = admin_commission.revenue_to_admin
                
                # Apply referral deduction
                admin_commission.referral_deduction = reward.reward_amount
                admin_commission.revenue_to_admin = admin_commission.original_revenue - reward.reward_amount
                admin_commission.save()
                
                print(f"✅ Admin commission updated: deducted ₹{reward.reward_amount}")
                logger.info(f"Deducted ₹{reward.reward_amount} from admin commission for bus booking {instance.booking_id}")
                
            except AdminCommission.DoesNotExist:
                print(f"❌ Admin commission not found for bus booking {instance.booking_id}")
                logger.error(f"Admin commission not found for bus booking {instance.booking_id}")

            # Mark reward as credited
            reward.status = 'credited'
            reward.credited_at = timezone.now()
            reward.save()
            
            print("✅ Reward marked as credited")
            logger.info(f"Added ₹{reward.reward_amount} to referrer {reward.referrer.id} wallet for completed bus trip {instance.booking_id}")

        elif current_status == 'cancelled':
            print("❌ Processing trip cancellation...")
            
            # Cancel the reward
            reward.status = 'cancelled'
            reward.save()
            
            print("✅ Reward marked as cancelled")

            # Reset referral_used for the referred user's wallet
            try:
                referred_wallet = Wallet.objects.get(user=reward.referred_user)
                referred_wallet.referral_used = False
                referred_wallet.save()
                
                print(f"✅ Reset referral_used for user {reward.referred_user.id}")
                logger.info(f"Reset referral_used for user {reward.referred_user.id} due to cancelled bus trip {instance.booking_id}")
                
            except Wallet.DoesNotExist:
                print(f"❌ Wallet not found for referred user {reward.referred_user.id}")
                logger.warning(f"Wallet not found for referred user {reward.referred_user.id}")
        
        else:
            print(f"⚪ Trip status '{current_status}' - no action needed")
            
    except Exception as e:
        print(f"🚨 Error in bus booking signal: {str(e)}")
        logger.error(f"Error in bus booking signal for booking {instance.booking_id}: {str(e)}")


@receiver(post_save, sender=PackageBooking)
def handle_package_trip_status_change(sender, instance, created, **kwargs):
    """
    Handle referral rewards when package booking trip status changes
    """
    # Skip for new bookings
    if created:
        return
    
    print(f"🔥 PACKAGE BOOKING SIGNAL TRIGGERED for booking {instance.booking_id}")
    logger.info(f"Package booking signal triggered for booking {instance.booking_id}")
    
    # Get the current state from database to compare
    try:
        current_status = instance.trip_status
        print(f"📊 Current trip status: {current_status}")
        
        # Check if there's a pending referral reward for this booking
        try:
            reward = ReferralRewardTransaction.objects.get(
                booking_type='package',
                booking_id=instance.booking_id,  # Use booking_id instead of pk
                status='pending'
            )
            print(f"✅ Found pending reward: {reward.id} for amount ₹{reward.reward_amount}")
        except ReferralRewardTransaction.DoesNotExist:
            print(f"❌ No pending referral reward found for package booking {instance.booking_id}")
            logger.info(f"No pending referral reward found for package booking {instance.booking_id}")
            return
        except ReferralRewardTransaction.MultipleObjectsReturned:
            print(f"⚠️ Multiple pending rewards found for package booking {instance.booking_id}")
            logger.warning(f"Multiple pending rewards found for package booking {instance.booking_id}")
            reward = ReferralRewardTransaction.objects.filter(
                booking_type='package',
                booking_id=instance.booking_id,
                status='pending'
            ).first()

        if current_status == 'completed':
            print("💰 Processing trip completion...")
            
            # Credit money to referrer
            referrer_wallet, created = Wallet.objects.get_or_create(user=reward.referrer)
            old_balance = referrer_wallet.balance
            referrer_wallet.balance += reward.reward_amount
            referrer_wallet.save()
            
            print(f"✅ Referrer wallet updated: ₹{old_balance} → ₹{referrer_wallet.balance}")

            # Update admin commission - deduct referral amount
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='package',
                    booking_id=instance.booking_id  # Use booking_id instead of pk
                )
                
                # Store original revenue if not already stored
                if admin_commission.original_revenue is None:
                    admin_commission.original_revenue = admin_commission.revenue_to_admin
                
                # Apply referral deduction
                admin_commission.referral_deduction = reward.reward_amount
                admin_commission.revenue_to_admin = admin_commission.original_revenue - reward.reward_amount
                admin_commission.save()
                
                print(f"✅ Admin commission updated: deducted ₹{reward.reward_amount}")
                logger.info(f"Deducted ₹{reward.reward_amount} from admin commission for package booking {instance.booking_id}")
                
            except AdminCommission.DoesNotExist:
                print(f"❌ Admin commission not found for package booking {instance.booking_id}")
                logger.error(f"Admin commission not found for package booking {instance.booking_id}")

            # Mark reward as credited
            reward.status = 'credited'
            reward.credited_at = timezone.now()
            reward.save()
            
            print("✅ Reward marked as credited")
            logger.info(f"Added ₹{reward.reward_amount} to referrer {reward.referrer.id} wallet for completed package trip {instance.booking_id}")

        elif current_status == 'cancelled':
            print("❌ Processing trip cancellation...")
            
            # Cancel the reward
            reward.status = 'cancelled'
            reward.save()
            
            print("✅ Reward marked as cancelled")

            # Reset referral_used for the referred user's wallet
            try:
                referred_wallet = Wallet.objects.get(user=reward.referred_user)
                referred_wallet.referral_used = False
                referred_wallet.save()
                
                print(f"✅ Reset referral_used for user {reward.referred_user.id}")
                logger.info(f"Reset referral_used for user {reward.referred_user.id} due to cancelled package trip {instance.booking_id}")
                
            except Wallet.DoesNotExist:
                print(f"❌ Wallet not found for referred user {reward.referred_user.id}")
                logger.warning(f"Wallet not found for referred user {reward.referred_user.id}")
        
        else:
            print(f"⚪ Trip status '{current_status}' - no action needed")
            
    except Exception as e:
        print(f"🚨 Error in package booking signal: {str(e)}")
        logger.error(f"Error in package booking signal for booking {instance.booking_id}: {str(e)}")