from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import string
import random


# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, mobile=None, email=None, password=None, **extra_fields):
        if not mobile and not email:
            raise ValueError("Users must have a mobile number or email")

        extra_fields.setdefault("role", "user")
        user = self.model(mobile=mobile, email=self.normalize_email(email), **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, mobile=None, email=None, password=None, **extra_fields):
        """Creates and returns a superuser with admin privileges."""
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not password:
            raise ValueError("Superuser must have a password.")

        return self.create_user(mobile=mobile, email=email, password=password, **extra_fields)
    

def generate_referral_code(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))


class User(AbstractBaseUser, PermissionsMixin):
    ADMIN = 'admin'
    VENDOR = 'vendor'   
    USER = 'user'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (VENDOR, 'Vendor'),
        (USER, 'User'),
    ]

    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=USER)
    is_google_user = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    referral_code = models.CharField(max_length=7, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    city = models.CharField(max_length=255, null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if not self.referral_code:
            while True:
                code = generate_referral_code()
                if not User.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return self.mobile if self.mobile else (self.email if self.email else "Unnamed User")




class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    email_address = models.EmailField(unique=True)
    # phone_no = models.CharField(max_length=15)
    phone_no = models.CharField(max_length=15, blank=True, null=True)

    travels_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    pincode = models.CharField(max_length=10)
    district = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, blank=True, null=True)
  


    def __str__(self):
        return self.full_name



class Advertisement(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="advertisements/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Advertisement - {self.title}"


class LimitedDeal(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name="limited_deals")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Limited Deal - {self.title}"


class LimitedDealImage(models.Model):
    deal = models.ForeignKey(LimitedDeal, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="limited_deals/")

    def __str__(self):
        return f"Image for {self.deal.title}"


class FooterSection(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name="footer_sections")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="footer_sections/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Footer Section - {self.title}"


 


class Sight(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='sight_images/', null=True, blank=True)
    description = models.TextField()
    season_description = models.TextField()

    def __str__(self):
        return self.title


class Experience(models.Model):
    sight = models.ForeignKey(Sight, related_name='experiences', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='experiences/')
    description = models.TextField()

    def __str__(self):
        return f"Experience for {self.sight.title}"


class SeasonTime(models.Model):
    sight = models.ForeignKey(Sight, related_name='seasons', on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date = models.DateField()
    description = models.TextField()

    icon1 = models.ImageField(upload_to='season_icons/', null=True, blank=True)
    icon1_description = models.CharField(max_length=255, blank=True)

    icon2 = models.ImageField(upload_to='season_icons/', null=True, blank=True)
    icon2_description = models.CharField(max_length=255, blank=True)

    icon3 = models.ImageField(upload_to='season_icons/', null=True, blank=True)
    icon3_description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Season from {self.from_date} to {self.to_date} for {self.sight.title}"



class AdminCommissionSlab(models.Model):
    min_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    advance_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        ordering = ['min_amount']

    def __str__(self):
        return f"{self.min_amount} - {self.max_amount} => {self.commission_percentage}%"


class AdminCommission(models.Model):
    booking_type = models.CharField(max_length=20, choices=[('bus', 'Bus'), ('package', 'Package')])
    booking_id = models.IntegerField()
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    revenue_to_admin = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking_type} Booking ID {self.booking_id} - Admin Revenue {self.revenue_to_admin}"
