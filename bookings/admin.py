from django.contrib import admin
from .models import BusBooking,PackageBooking,Travelers,BusDriverDetail

# Register your models here.
admin.site.register(BusBooking)
admin.site.register(PackageBooking)
admin.site.register(Travelers)
admin.site.register(BusDriverDetail)