from django.db import models
from django.contrib.auth import get_user_model
from vendors.models import Bus,Package
from django.core.validators import MinValueValidator


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

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    referred_by = models.CharField(max_length=20, blank=True, null=True)
    referral_used = models.BooleanField(default=False)
    wallet_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.name}'s Wallet"
    
class ReferralRewardTransaction(models.Model):
    BOOKING_TYPES = (
        ('bus', 'Bus Booking'),
        ('package', 'Package Booking'),
    )
    REWARD_STATUS = (
        ('pending', 'Pending'),
        ('credited', 'Credited'),
        ('cancelled', 'Cancelled'),
    )
    
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rewards')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='used_referrals')
    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPES)
    booking_id = models.PositiveIntegerField()
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=REWARD_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    credited_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Referral reward of ₹{self.reward_amount} for {self.referrer.name}"

    class Meta:
        unique_together = ('referred_user', 'booking_type', 'booking_id')