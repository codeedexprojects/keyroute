from django.db import models

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

    def __str__(self):
        return self.bus_name


class BusImage(models.Model):
    bus = models.ForeignKey(Bus, related_name='images', on_delete=models.CASCADE)
    bus_view_image = models.ImageField(upload_to='bus_views/', null=True, blank=True)

    def __str__(self):
        return f"Image for {self.bus.bus_name}"
