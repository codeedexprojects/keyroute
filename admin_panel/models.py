from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, mobile=None, email=None, password=None, **extra_fields):
        if not mobile and not email:
            raise ValueError("Users must have a mobile number or email")

        extra_fields.setdefault("role", "user")  # Default role to 'user' if not provided
        user = self.model(mobile=mobile, email=self.normalize_email(email), **extra_fields)

        if password:
            user.set_password(password)  # Vendors/Admins use passwords
        else:
            user.set_unusable_password()  # Normal users using OTP

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


class User(AbstractBaseUser, PermissionsMixin):
    ADMIN = 'admin'
    VENDOR = 'vendor'   
    USER = 'user'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (VENDOR, 'Vendor'),
        (USER, 'User'),
    ]

    email = models.EmailField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=USER)
    is_google_user = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "mobile"  # Default login with mobile
    REQUIRED_FIELDS = []  # No required fields

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






