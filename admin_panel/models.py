from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

# Create your models here.

class UserManager(BaseUserManager):
    """Custom user manager where phone_number is the unique identifier"""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("The Phone Number field is required")
        
        extra_fields.setdefault("is_active", True)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone_number, password, **extra_fields)

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

    objects = UserManager()  # Set custom user manager

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

    def __str__(self):
        return self.full_name








