from django.db import models
from vendors.models import Package
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.contrib.auth import get_user_model
from datetime import date

# Create your models here.

User = get_user_model()

class Booking(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    total_adults = models.PositiveIntegerField(default=0)
    total_children = models.PositiveIntegerField(default=0)
    total_males = models.PositiveIntegerField(default=0)
    total_females = models.PositiveIntegerField(default=0)
    total_rooms = models.PositiveIntegerField(default=0)
    total_travelers = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Booking #{self.id} - {self.package.places} ({self.start_date})"

class Traveler(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='travelers')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    place = models.CharField(max_length=100)
    dob = models.DateField(null=True, blank=True)
    id_proof = models.FileField(upload_to='travelers/id_proofs/', null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} - Booking #{self.booking.id}"

class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('advance', 'Advance Payment'),
        ('remaining', 'Remaining Payment'),
        ('full', 'Full Payment'),
    )
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=15, choices=PAYMENT_TYPE_CHOICES)
    payment_date = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"Payment of ₹{self.amount} for Booking #{self.booking.id}"

class CancellationPolicy(models.Model):
    package = models.OneToOneField(Package, on_delete=models.CASCADE, related_name='cancellation_policy')
    description = models.TextField()
    is_advance_refundable = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Cancellation Policy for {self.package.places}"