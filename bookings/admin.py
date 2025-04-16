from django.contrib import admin
from .models import BusBooking,PackageBooking,Traveler

# Register your models here.
admin.site.register(BusBooking)
admin.site.register(PackageBooking)
admin.site.register(Traveler)