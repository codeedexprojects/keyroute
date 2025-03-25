from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ADMIN = 'admin'
    VENDOR = 'vendor'
    USER = 'user'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (VENDOR, 'Vendor'),
        (USER, 'User'),
    ]

    username = None  # Remove default username field
    email = models.EmailField(unique=True, blank=True, null=True)  # Optional email
    phone_number = models.CharField(max_length=15, unique=True)  # Primary login field
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=USER)
    updated_at = models.DateTimeField(auto_now=True)
    is_google_user = models.BooleanField(default=False)  # Identifies Google signups

    USERNAME_FIELD = 'phone_number'  # Login using phone number
    REQUIRED_FIELDS = []  # No required fields other than phone_number

    def __str__(self):
        return f'{self.phone_number} ({self.get_role_display()})'

    



class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    email_address = models.EmailField(unique=True)
    phone_no = models.CharField(max_length=15)
    travels_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    pincode = models.CharField(max_length=10)
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.full_name








