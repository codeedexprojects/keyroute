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
    



