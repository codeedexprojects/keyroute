from django.contrib import admin
from .models import *
# Register your models here.


admin.site.register(OTP)
admin.site.register(Bus)
admin.site.register(BusImage)
admin.site.register(PackageCategory)
admin.site.register(PackageSubCategory)
admin.site.register(Package)
admin.site.register(Amenity)



admin.site.register(DayPlan)
admin.site.register(Place)
admin.site.register(PlaceImage)
admin.site.register(Stay)
admin.site.register(StayImage)
admin.site.register(Meal)
admin.site.register(MealImage)
admin.site.register(Activity)
admin.site.register(ActivityImage)

admin.site.register(BusFeature)
admin.site.register(VendorBankDetail)
admin.site.register(VendorNotification)


