from django.db import models
from django.core.validators import FileExtensionValidator
from django.db.models import Avg
# Create your models here.

from django.utils import timezone
import random
from admin_panel.models import *

class OTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_otp(self):
        otp = str(random.randint(100000, 999999))  
        self.otp_code = otp
        self.created_at = timezone.now()
        self.save()
        return otp

    def is_valid(self):
        return timezone.now() - self.created_at < timezone.timedelta(minutes=5)
    

class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.ImageField(
        upload_to='amenity/icons/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg'])],
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


class BusFeature(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name




    def __str__(self):
        return self.name


class Bus(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('maintenance', 'Under Maintenance'),
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    bus_name = models.CharField(max_length=255)
    bus_number = models.CharField(max_length=20, unique=True)
    capacity = models.IntegerField()
    vehicle_description = models.TextField()
    travels_logo = models.ImageField(upload_to='travels_logos/', null=True, blank=True)   
    rc_certificate = models.FileField(upload_to='rc_certificates/')
    license = models.FileField(upload_to='licenses/')
    contract_carriage_permit = models.FileField(upload_to='permits/')
    passenger_insurance = models.FileField(upload_to='insurance/', null=True, blank=True)
    vehicle_insurance = models.FileField(upload_to='insurance/')
    amenities = models.ManyToManyField(Amenity, related_name='buses', blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_price_km = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, help_text="KM included per day in base price")
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    night_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Additional charge per night",null=True, blank=True)
    features = models.ManyToManyField(BusFeature, related_name='buses', blank=True)
    minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    bus_type = models.CharField(max_length=50, blank=True, null=True)
    is_popular = models.BooleanField(default=False)

    @property
    def average_rating(self):
        avg = self.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0
    
    @property
    def total_reviews(self):
        return self.bus_reviews.count()
    
    def __str__(self):
        return self.bus_name


class BusTravelImage(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='travel_images')
    image = models.ImageField(upload_to='bus_travel_images/')

    def __str__(self):
        return f"Image for {self.bus.bus_name} ({self.bus.bus_number})"







class BusImage(models.Model):
    bus = models.ForeignKey(Bus, related_name='images', on_delete=models.CASCADE)
    bus_view_image = models.ImageField(upload_to='bus_views/', null=True, blank=True)

    def __str__(self):
        return f"Image for {self.bus.bus_name}"





class PackageCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to='package_categories/', null=True, blank=True)

    def __str__(self):
        return self.name



class PackageSubCategory(models.Model):
    category = models.ForeignKey(PackageCategory, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to='package_subcategories/', null=True, blank=True)

    def __str__(self):
        return self.name


class Package(models.Model):

    STATUS_CHOICES = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('expired', 'Expired'),
    )


    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(PackageSubCategory, on_delete=models.CASCADE, related_name="packages")
    header_image = models.ImageField(
        upload_to='packages/header/',
        validators=[FileExtensionValidator(['jpg', 'png'])]
    )
    places = models.CharField(max_length=255)
    days = models.PositiveIntegerField(default=0)
    ac_available = models.BooleanField(default=True, verbose_name="AC Available")
    guide_included = models.BooleanField(default=False, verbose_name="Includes Guide")
    buses = models.ManyToManyField(Bus)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bus_location = models.CharField(max_length=255, blank=True, null=True)
    price_per_person = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    extra_charge_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')


    @property
    def average_rating(self):
        avg = self.package_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0
    
    @property
    def total_reviews(self):
        return self.package_reviews.count()
    
    def __str__(self):
        return self.name

    def __str__(self):
        return f"{self.sub_category.name} - {self.places}"


class PackageImage(models.Model):
    package = models.ForeignKey('Package', on_delete=models.CASCADE, related_name='package_images')
    image = models.ImageField(
        upload_to='packages/images/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)






class DayPlan(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='day_plans')
    day_number = models.PositiveIntegerField()
    description = models.TextField(blank=True, null=True)
    night = models.BooleanField(default=False)


class Place(models.Model):
    day_plan = models.ForeignKey(DayPlan, on_delete=models.CASCADE, related_name='places')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='packages/places/')



class Stay(models.Model):
    day_plan = models.OneToOneField(DayPlan, on_delete=models.CASCADE, related_name='stay')
    hotel_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)  
    is_ac = models.BooleanField(default=False, blank=True, null=True)
    has_breakfast = models.BooleanField(default=False, blank=True, null=True) 


class StayImage(models.Model):
    stay = models.ForeignKey(Stay, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='packages/stays/')



class Meal(models.Model):
    day_plan = models.ForeignKey(DayPlan, on_delete=models.CASCADE, related_name='meals')
    type = models.CharField(max_length=50, choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner')])
    description = models.TextField(blank=True, null=True)
    restaurant_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    time = models.TimeField(blank=True, null=True)



class MealImage(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='packages/meals/')


class Activity(models.Model):
    day_plan = models.ForeignKey(DayPlan, on_delete=models.CASCADE, related_name='activities')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

class ActivityImage(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='packages/activities/')





class VendorBankDetail(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name="bank_detail")
    
    holder_name = models.CharField(max_length=100, blank=True, null=True)
    payout_mode = models.CharField(max_length=50,blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20,blank=True, null=True)
    email_id = models.EmailField(blank=True, null=True)
    account_number = models.CharField(max_length=50,blank=True, null=True)

    payout_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    customer_id = models.CharField(max_length=100, blank=True, null=True)
    pay_id = models.CharField(max_length=100, blank=True, null=True)
    payout_narration = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.vendor.full_name} - {self.account_number}"





class VendorNotification(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='notifications')
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)  # Optional but useful

    def __str__(self):
        return f"Notification for {self.vendor.full_name} - {self.description[:30]}..."






class VendorBusyDate(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='busy_dates')
    buses = models.ManyToManyField('Bus', related_name='busy_dates')
    date = models.DateField()
    from_time = models.TimeField(blank=True, null=True)
    to_time = models.TimeField(blank=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'date', 'from_time', 'to_time')
        ordering = ['-date']

    def __str__(self):
        if self.from_time and self.to_time:
            return f"{self.vendor.user.name} - {self.date} ({self.from_time} to {self.to_time})"
        return f"{self.vendor.user.name} - {self.date} (Full Day)"