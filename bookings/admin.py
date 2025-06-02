from django.contrib import admin
from .models import BusBooking,PackageBooking,Travelers,BusDriverDetail,PackageDriverDetail,UserBusSearch

# Register your models here.
admin.site.register(BusBooking)
admin.site.register(PackageBooking)
admin.site.register(Travelers)
admin.site.register(BusDriverDetail)
admin.site.register(PackageDriverDetail)
admin.site.register(UserBusSearch)