from django.contrib import admin
from .models import *
# Register your models here.


admin.site.register(OTP)
admin.site.register(Bus)
admin.site.register(BusImage)
admin.site.register(PackageCategory)
admin.site.register(PackageSubCategory)
admin.site.register(Package)