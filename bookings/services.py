from decimal import Decimal
from django.db import transaction
from users.models import Wallet
from .models import WalletTransaction
import uuid
import logging

logger = logging.getLogger(__name__)

class WalletTransactionService:
    
    @staticmethod
    def get_wallet_amount_used_for_booking(booking_id, booking_type, user):
        """Get the active wallet amount used for a specific booking"""
        try:
            wallet_transaction = WalletTransaction.objects.filter(
                booking_id=booking_id,
                booking_type=booking_type,
                user=user,
                transaction_type='applied',
                is_active=True
            ).latest('created_at')
            return wallet_transaction.amount
        except WalletTransaction.DoesNotExist:
            return Decimal('0.00')
    
    @staticmethod
    def has_wallet_been_applied(booking_id, booking_type, user):
        """Check if wallet has been applied to a booking and is still active"""
        return WalletTransaction.objects.filter(
            booking_id=booking_id,
            booking_type=booking_type,
            user=user,
            transaction_type='applied',
            is_active=True
        ).exists()
    
    @staticmethod
    @transaction.atomic
    def apply_wallet_to_booking(user, booking_id, booking_type, wallet_amount, description=None):
        """Apply wallet amount to a booking and create transaction record"""
        try:
            # Get user's wallet
            wallet = Wallet.objects.select_for_update().get(user=user)
            
            # Validate wallet balance
            if wallet.balance < wallet_amount:
                raise ValueError("Insufficient wallet balance")
            
            # Create reference ID for tracking
            reference_id = str(uuid.uuid4())[:8]
            
            # Record balance before transaction
            balance_before = wallet.balance
            
            # Deduct from wallet
            wallet.balance -= wallet_amount
            balance_after = wallet.balance
            wallet.save()
            
            # Create transaction record
            wallet_transaction = WalletTransaction.objects.create(
                user=user,
                booking_id=booking_id,
                booking_type=booking_type,
                transaction_type='applied',
                amount=wallet_amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description or f"Applied to {booking_type} booking {booking_id}",
                reference_id=reference_id,
                is_active=True
            )
            
            logger.info(f"Applied wallet ₹{wallet_amount} to {booking_type} booking {booking_id} for user {user.name}")
            
            return wallet_transaction, wallet
            
        except Exception as e:
            logger.error(f"Error applying wallet to booking: {str(e)}")
            raise e
    
    @staticmethod
    @transaction.atomic
    def remove_wallet_from_booking(user, booking_id, booking_type, description=None):
        """Remove wallet amount from a booking and restore to wallet - Updates existing transaction instead of creating new one"""
        try:
            # Get the active wallet transaction for this booking
            wallet_transaction = WalletTransaction.objects.select_for_update().get(
                booking_id=booking_id,
                booking_type=booking_type,
                user=user,
                transaction_type='applied',
                is_active=True
            )
            
            # Get user's wallet
            wallet = Wallet.objects.select_for_update().get(user=user)
            
            # Get the wallet amount from the transaction record
            wallet_amount_restored = wallet_transaction.amount
            
            # Restore wallet balance
            wallet.balance += wallet_amount_restored
            wallet.save()
            
            # Update the existing transaction to mark as removed/inactive
            wallet_transaction.is_active = False
            wallet_transaction.transaction_type = 'removed'
            if description:
                wallet_transaction.description = description
            else:
                wallet_transaction.description = f"Removed from {booking_type} booking {booking_id}"
            wallet_transaction.save()
            
            logger.info(f"Removed wallet ₹{wallet_amount_restored} from {booking_type} booking {booking_id} for user {user.name}")
            
            return wallet_transaction, wallet, wallet_amount_restored
            
        except WalletTransaction.DoesNotExist:
            raise ValueError("No active wallet transaction found for this booking")
        except Exception as e:
            logger.error(f"Error removing wallet from booking: {str(e)}")
            raise e
    
    @staticmethod
    def get_user_wallet_transactions(user, limit=None):
        """Get wallet transactions for a user"""
        queryset = WalletTransaction.objects.filter(user=user).order_by('-created_at')
        if limit:
            queryset = queryset[:limit]
        return queryset
    
    @staticmethod
    def is_wallet_currently_used(user):
        """Check if user has any active wallet transactions (wallet is currently being used)"""
        return WalletTransaction.objects.filter(
            user=user,
            transaction_type='applied',
            is_active=True
        ).exists()