from django.db import models
from vendors.models import Package, Bus
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.contrib.auth import get_user_model
from datetime import date
import random
import datetime
from admin_panel.models import *

User = get_user_model()

class BaseBooking(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('cancelled', 'Cancelled'),
    )
    BOOKING_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )
    TRIP_STATUS_CHOICES = (
        ('not_started','Not Started'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField(null=True,blank=True)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True,blank=True)
    first_time_discount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True,blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    payout_status = models.BooleanField(default=False)
    payout = models.ForeignKey('PayoutHistory', on_delete=models.SET_NULL, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending') 
    trip_status = models.CharField(max_length=20, choices=TRIP_STATUS_CHOICES, default='not_started')
    created_at = models.DateTimeField(auto_now_add=True)
    cancellation_reason = models.CharField(max_length=250,null=True,blank=True)
    total_travelers = models.PositiveIntegerField(default=0,null=True,blank=True)
    male = models.PositiveIntegerField(default=0)
    female = models.PositiveIntegerField(default=0)
    children = models.PositiveIntegerField(default=0)
    from_location = models.CharField(max_length=255, null=True, blank=True)
    to_location = models.CharField(max_length=255, null=True, blank=True)
    
    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        abstract = True
        
    @property
    def balance_amount(self):
        return self.total_amount - self.paid_amount
    
    def generate_unique_booking_id(self):
        while True:
            booking_id = random.randint(10000, 99999)
            if not self.__class__.objects.filter(booking_id=booking_id).exists():
                return booking_id

    def update_payment_status(self):
        """Update payment status based on paid amount"""
        if self.paid_amount == 0:
            self.payment_status = 'pending'
        elif self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
        else:
            self.payment_status = 'partial'
        self.save()

    def save(self, *args, **kwargs):
        if not hasattr(self, 'booking_id') or not self.booking_id:
            self.booking_id = self.generate_unique_booking_id()
        
        if self.paid_amount == 0:
            self.payment_status = 'pending'
        elif self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
        else:
            self.payment_status = 'partial'
            
        super().save(*args, **kwargs)


class BusBooking(BaseBooking):
    booking_id = models.PositiveIntegerField(unique=True, editable=False)
    bus = models.ForeignKey(Bus, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    from_lat = models.FloatField()
    from_lon = models.FloatField()
    to_lat = models.FloatField(null=True, blank=True)
    to_lon = models.FloatField(null=True, blank=True)
    return_date = models.DateField(null=True,blank=True)
    pick_up_time = models.TimeField(null=True,blank=True)
    end_date = models.DateField(null=True, blank=True, help_text="End date of the trip")
    night_allowance_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    base_price_days = models.PositiveIntegerField(default=0, help_text="Number of additional days charged at base price")
    total_distance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total distance including stops")
    
    def __str__(self):
        return f"Bus Booking #{self.booking_id} - {self.from_location} to {self.to_location} ({self.start_date})"

    def save(self, *args, **kwargs):
        if self.bus and not self.total_travelers:
            self.total_travelers = self.bus.capacity
        super().save(*args, **kwargs)


class PackageBooking(BaseBooking):
    booking_id = models.PositiveIntegerField(unique=True, editable=False)
    rooms = models.IntegerField(default=1)
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    
    def __str__(self):
        return f"Package Booking #{self.booking_id} - {self.package.places} ({self.created_at})"


class PaymentTransaction(models.Model):
    TRANSACTION_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    
    booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    package_booking = models.ForeignKey(PackageBooking, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Transaction {self.razorpay_order_id} - {self.amount}"


class Travelers(models.Model):
    """Model for individual travelers associated with a booking"""
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),                 
        ('O', 'Other'),
    )
    
    # Generic foreign key relationship
    bus_booking = models.ForeignKey(BusBooking, on_delete=models.SET_NULL, 
                                    related_name='travelers', null=True, blank=True)
    package_booking = models.ForeignKey(PackageBooking, on_delete=models.SET_NULL, 
                                       related_name='travelers', null=True, blank=True)
    
    # Personal details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    age = models.PositiveBigIntegerField(null=True,blank=True)
    dob = models.DateField(null=True, blank=True)
    
    # Contact information
    email = models.EmailField(blank=True, null=True)
    mobile = models.CharField(max_length=15, null=True, blank=True)
    
    # Location details
    place = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    
    # Identity proof
    id_proof = models.FileField(
        upload_to='travelers/id_proofs/', 
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        booking_id = self.bus_booking.booking_id if self.bus_booking else self.package_booking.booking_id
        booking_type = "Bus" if self.bus_booking else "Package"
        return f"{self.first_name} {self.last_name or ''} - {booking_type} #{booking_id}"
    
    def clean(self):
        """Ensure traveler is associated with exactly one booking type"""
        from django.core.exceptions import ValidationError
        
        if self.bus_booking and self.package_booking:
            raise ValidationError("A traveler can't be associated with both bus and package bookings")
        if not self.bus_booking and not self.package_booking:
            raise ValidationError("A traveler must be associated with either a bus or package booking")
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(bus_booking__isnull=False, package_booking__isnull=True) | 
                    models.Q(bus_booking__isnull=True, package_booking__isnull=False)
                ),
                name="one_booking_type_only"
            )
        ]


        



class BusDriverDetail(models.Model):
    bus_booking = models.OneToOneField('BusBooking', on_delete=models.CASCADE, related_name='driver_detail')
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, null=True, blank=True) 
    place = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    driver_image = models.ImageField(upload_to='driver_images/')
    license_image = models.ImageField(upload_to='license_images/')
    experience = models.PositiveIntegerField(help_text="Experience in years")
    age = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class PackageDriverDetail(models.Model):
    package_booking = models.OneToOneField(PackageBooking, on_delete=models.CASCADE, related_name='driver_detail')
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, null=True, blank=True) 
    place = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    driver_image = models.ImageField(upload_to='driver_images/')
    license_image = models.ImageField(upload_to='license_images/')
    experience = models.PositiveIntegerField(help_text="Experience in years")
    age = models.PositiveIntegerField()

    def __str__(self):
        return self.name
    

class UserBusSearch(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bus_search")
    from_lat = models.FloatField(null=False, blank=False)
    from_lon = models.FloatField(null=False, blank=False)
    to_lat = models.FloatField(null=True, blank=True)
    to_lon = models.FloatField(null=True, blank=True)
    seat = models.IntegerField(null=True, blank=True)
    ac = models.BooleanField(default=False)
    pick_up_date = models.DateField(null=True, blank=True)
    pick_up_time = models.TimeField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    search = models.CharField(max_length=255, null=True, blank=True)
    pushback = models.BooleanField(default=False)
    from_location = models.CharField(max_length=255, null=True, blank=True)
    to_location = models.CharField(max_length=255, null=True, blank=True)




class PayoutHistory(models.Model):
    PAYOUT_MODES = (
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('other', 'Other'),
    )

    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    payout_date = models.DateTimeField(auto_now_add=True)
    payout_mode = models.CharField(max_length=20, choices=PAYOUT_MODES)
    payout_reference = models.CharField(max_length=100, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    admin_commission = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Payout #{self.id} to {self.vendor.full_name}"

class PayoutBooking(models.Model):
    payout = models.ForeignKey(PayoutHistory, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    booking_type = models.CharField(max_length=10, choices=[('bus', 'Bus'), ('package', 'Package')])
    booking_id = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.booking_type} booking #{self.booking_id}"
    






class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('applied', 'Applied to Booking'),
        ('removed', 'Removed from Booking'),
        ('refund', 'Refunded'),
        ('added', 'Added to Wallet'),
        ('deducted', 'Deducted from Wallet'),
    ]
    
    BOOKING_TYPES = [
        ('bus', 'Bus Booking'),
        ('package', 'Package Booking'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')
    booking_id = models.CharField(max_length=100)
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPES)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)  # For tracking related transactions
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'booking_id', 'booking_type']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.name} - {self.transaction_type} - ₹{self.amount} - {self.booking_type} ({self.booking_id})"




class BusBookingStop(models.Model):
    """Model to store intermediate stops for bus bookings"""
    booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, related_name='stops')
    stop_order = models.PositiveIntegerField(help_text="Order of the stop in the journey")
    location_name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    distance_from_previous = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Distance from previous point in km")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['stop_order']
        unique_together = ('booking', 'stop_order')
    
    def __str__(self):
        return f"Stop {self.stop_order}: {self.location_name} for Booking #{self.booking.booking_id}"


class UserBusSearchStop(models.Model):
    """Model to store intermediate stops during search"""
    user_search = models.ForeignKey(UserBusSearch, on_delete=models.CASCADE, related_name='search_stops')
    stop_order = models.PositiveIntegerField(help_text="Order of the stop in the journey")
    location_name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['stop_order']
        unique_together = ('user_search', 'stop_order')
    
    def __str__(self):
        return f"Search Stop {self.stop_order}: {self.location_name}"






