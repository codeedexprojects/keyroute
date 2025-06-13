from decimal import Decimal
from django.db import transaction
from django.utils import timezone
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
        try:
            wallet = Wallet.objects.select_for_update().get(user=user)

            if wallet.balance < wallet_amount:
                raise ValueError("Insufficient wallet balance")

            reference_id = str(uuid.uuid4())[:8]
            balance_before = wallet.balance

            wallet.balance -= wallet_amount
            wallet.wallet_used = True
            balance_after = wallet.balance
            wallet.save()

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

            return wallet_transaction, wallet

        except Exception as e:
            logger.error(f"Error applying wallet to booking: {str(e)}")
            raise e
    
    @staticmethod
    @transaction.atomic
    def remove_wallet_from_booking(user, booking_id, booking_type, description=None):
        try:
            wallet_transaction = WalletTransaction.objects.select_for_update().get(
                booking_id=booking_id,
                booking_type=booking_type,
                user=user,
                transaction_type='applied',
                is_active=True
            )

            wallet = Wallet.objects.select_for_update().get(user=user)
            wallet_amount_restored = wallet_transaction.amount

            wallet.balance += wallet_amount_restored
            wallet.wallet_used = False
            wallet.save()

            wallet_transaction.is_active = False
            wallet_transaction.transaction_type = 'removed'
            wallet_transaction.balance_after = wallet.balance
            wallet_transaction.description = description or f"Removed from {booking_type} booking {booking_id}"
            wallet_transaction.updated_at = timezone.now()
            wallet_transaction.save()

            return wallet_transaction, wallet, wallet_amount_restored

        except WalletTransaction.DoesNotExist:
            raise ValueError("No active wallet transaction found for this booking")
        except Exception as e:
            logger.error(f"Error removing wallet from booking: {str(e)}")
            raise e
    
    @staticmethod
    def get_user_wallet_transactions(user, limit=None):
        """Get wallet transactions for a user - shows all transactions regardless of status"""
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
    
    @staticmethod
    def get_active_wallet_transactions(user):
        """Get all active wallet transactions for a user"""
        return WalletTransaction.objects.filter(
            user=user,
            transaction_type='applied',
            is_active=True
        ).order_by('-created_at')
    
    @staticmethod
    def get_wallet_transaction_by_booking(booking_id, booking_type, user):
        """Get wallet transaction for a specific booking"""
        try:
            return WalletTransaction.objects.get(
                booking_id=booking_id,
                booking_type=booking_type,
                user=user,
                transaction_type='applied',
                is_active=True
            )
        except WalletTransaction.DoesNotExist:
            return None