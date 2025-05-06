from django.db import models
from django.contrib.auth import get_user_model
from vendors.models import Bus,Package


# Create your models here.
User = get_user_model()


# class Review(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])  # 1 to 5 rating
#     comment = models.TextField(blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f'Review by {self.user.mobile} - {self.rating} Stars'

class Favourite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, null=True, blank=True)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = [
            ('user', 'bus'),
            ('user', 'package'),
        ]

class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.user.name}'s Wallet (₹{self.balance})"

class ReferralTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )
    
    REFERRAL_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_transactions')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_by_transactions')
    booking_type = models.CharField(max_length=10, choices=(('bus', 'Bus'), ('package', 'Package')))
    booking_id = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES, default='credit')
    status = models.CharField(max_length=20, choices=REFERRAL_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Referral: {self.user.name} -> {self.referred_user.name} ({self.status})"
