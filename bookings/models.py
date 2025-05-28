from django.db import models
from vendors.models import Package, Bus
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.contrib.auth import get_user_model
from datetime import date
import random

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
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending') 
    trip_status = models.CharField(max_length=20, choices=TRIP_STATUS_CHOICES, default='ongoing')

    created_at = models.DateTimeField(auto_now_add=True)
    cancelation_reason = models.CharField(max_length=250,null=True,blank=True)
    total_travelers = models.PositiveIntegerField(default=0)
    male  = models.PositiveIntegerField(default=1)
    female  = models.PositiveIntegerField(default=1)
    children  = models.PositiveIntegerField(default=1)
    from_location = models.CharField(max_length=150)
    to_location = models.CharField(max_length=150)
    
    class Meta:
        abstract = True
        
    @property
    def balance_amount(self):
        return self.total_amount - self.advance_amount
    
    def generate_unique_booking_id(self):
        while True:
            booking_id = random.randint(10000, 99999)
            if not self.__class__.objects.filter(booking_id=booking_id).exists():
                return booking_id

    def save(self, *args, **kwargs):
        if not self.booking_id:
            self.booking_id = self.generate_unique_booking_id()
        super().save(*args, **kwargs)
    

class BusBooking(BaseBooking):
    booking_id = models.PositiveIntegerField(unique=True, editable=False)
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='bookings')
    one_way = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Bus Booking #{self.booking_id} - {self.from_location} to {self.to_location} ({self.start_date})"

class PackageBooking(BaseBooking):
    booking_id = models.PositiveIntegerField(unique=True, editable=False)
    rooms = models.IntegerField(default=1)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='bookings')
    
    def __str__(self):
        return f"Package Booking #{self.booking_id} - {self.package.places} ({self.created_at})"


class Travelers(models.Model):
    """Model for individual travelers associated with a booking"""
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),                 
        ('O', 'Other'),
    )
    
    # Generic foreign key relationship
    bus_booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, 
                                    related_name='travelers', null=True, blank=True)
    package_booking = models.ForeignKey(PackageBooking, on_delete=models.CASCADE, 
                                       related_name='travelers', null=True, blank=True)
    
    # Personal details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    age = models.PositiveBigIntegerField(default=1)
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
    user = models.ForeignKey(User,on_delete=models.CASCADE, related_name="user_bus_searches")
    one_way = models.BooleanField(default=True)
    from_lat = models.FloatField()
    from_lon = models.FloatField()
    to_lat = models.FloatField()
    to_lon = models.FloatField()
    seat = models.IntegerField()
    ac = models.BooleanField(default=False)
    pushback = models.BooleanField(default=False)