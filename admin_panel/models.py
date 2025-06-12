from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import string
import random
from .utils import generate_referral_code

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
    

class OTPSession(models.Model):
    """
    Model to store OTP session data instead of using cache
    """
    mobile = models.CharField(max_length=15)
    session_id = models.CharField(max_length=100, unique=True)
    is_new_user = models.BooleanField(default=False)
    name = models.CharField(max_length=150, null=True, blank=True)
    referral_code = models.CharField(max_length=10, null=True, blank=True)
    referrer = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_otp_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        # Optional index to improve lookup performance
        indexes = [
            models.Index(fields=['mobile']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"OTP Session for {self.mobile} - {self.session_id}"
        
    def is_expired(self):
        """Check if the OTP session has expired"""
        return timezone.now() > self.expires_at


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
    
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)

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
        if self.mobile:
            return self.mobile
        elif self.email:
            return self.email
        else:
            return "Unnamed User"

    class Meta:
        # Add constraint to ensure unique email when not null
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(email__isnull=False),
                name='unique_email_when_not_null'
            )
        ]




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
    subtitle = models.CharField(max_length=255, null=True, blank=True) 
    type = models.CharField(max_length=255, null=True, blank=True) 
    image = models.ImageField(upload_to="advertisements/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Advertisement - {self.title}"


class LimitedDeal(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    terms_and_conditions = models.TextField(null=True, blank=True)
    offer = models.CharField(max_length=100, null=True, blank=True)
    subtitle = models.CharField(max_length=255, blank=True, null=True) 


    def __str__(self):
        return f"Limited Deal - {self.title}"


class LimitedDealImage(models.Model):
    deal = models.ForeignKey(LimitedDeal, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="limited_deals/")

    def __str__(self):
        return f"Image for {self.deal.title}"



class ReferAndEarn(models.Model):
    image = models.ImageField(upload_to="refer_and_earn/")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Refer and Earn - ₹{self.price}"







class FooterSection(models.Model):
    main_image  = models.ImageField(upload_to="footer_sections/")
    package = models.ForeignKey('vendors.Package', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # def __str__(self):
    #     return f"Footer Section - {self.package.id}"

    def __str__(self):
        return f"Footer Section - Package {self.package.id}" if self.package else "Footer Section - No Package"



class FooterImage(models.Model):
    footer_section = models.ForeignKey(FooterSection, on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to="footer_sections/extra/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extra Image for Footer Section - {self.footer_section.id}"

 


class Sight(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    season_description = models.TextField()

    def __str__(self):
        return self.title


class SightImage(models.Model):
    sight = models.ForeignKey(Sight, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='sight_images/')

    def __str__(self):
        return f"Image for {self.sight.title}"

class Experience(models.Model):
    sight = models.ForeignKey(Sight, related_name='experiences', on_delete=models.CASCADE)
    header = models.CharField(max_length=255, blank=True, null=True)
    sub_header = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()

    def __str__(self):
        return f"Experience for {self.sight.title}"



class ExperienceImage(models.Model):
    experience = models.ForeignKey(Experience, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='experiences/')

    def __str__(self):
        return f"Image for {self.experience}"





class SeasonTime(models.Model):
    sight = models.ForeignKey(Sight, related_name='seasons', on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date = models.DateField()

    header = models.CharField(max_length=255, blank=True, null=True)

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
    original_revenue = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    referral_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking_type} Booking ID {self.booking_id} - Admin Revenue {self.revenue_to_admin}"
