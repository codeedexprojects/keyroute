from django.db import models
from admin_panel.models import User
from vendors.models import Bus
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class BusReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bus = models.ForeignKey(Bus, related_name="reviews", on_delete=models.CASCADE)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.bus.bus_name} by {self.user.username}"
