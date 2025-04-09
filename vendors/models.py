from django.db import models
from django.core.validators import FileExtensionValidator

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

    def __str__(self):
        return self.name




class Bus(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    bus_name = models.CharField(max_length=255)
    bus_number = models.CharField(max_length=20, unique=True)
    bus_type = models.CharField(max_length=50)
    capacity = models.IntegerField()
    vehicle_description = models.TextField()
    vehicle_rc_number = models.CharField(max_length=50)
    travels_logo = models.ImageField(upload_to='travels_logos/', null=True, blank=True)  # Moved here
    rc_certificate = models.FileField(upload_to='rc_certificates/')
    license = models.FileField(upload_to='licenses/')
    contract_carriage_permit = models.FileField(upload_to='permits/')
    passenger_insurance = models.FileField(upload_to='insurance/', null=True, blank=True)
    vehicle_insurance = models.FileField(upload_to='insurance/')
    amenities = models.ManyToManyField(Amenity, related_name='buses', blank=True)

    def __str__(self):
        return self.bus_name


class BusImage(models.Model):
    bus = models.ForeignKey(Bus, related_name='images', on_delete=models.CASCADE)
    bus_view_image = models.ImageField(upload_to='bus_views/', null=True, blank=True)

    def __str__(self):
        return f"Image for {self.bus.bus_name}"





class PackageCategory(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
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
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(PackageSubCategory, on_delete=models.CASCADE, related_name="packages")
    header_image = models.ImageField(
        upload_to='packages/header/',
        validators=[FileExtensionValidator(['jpg', 'png'])]
    )
    places = models.CharField(max_length=255)
    days = models.PositiveIntegerField(default=0)
    nights = models.PositiveIntegerField(default=0)
    ac_available = models.BooleanField(default=True, verbose_name="AC Available")
    guide_included = models.BooleanField(default=False, verbose_name="Includes Guide")
    buses = models.ManyToManyField(Bus)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sub_category.name} - {self.places}"