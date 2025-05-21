from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(User)
admin.site.register(Vendor)
admin.site.register(Advertisement)
admin.site.register(Experience)
admin.site.register(Sight)
admin.site.register(LimitedDeal)
admin.site.register(FooterSection)
admin.site.register(LimitedDealImage)
admin.site.register(AdminCommission)

admin.site.register(AdminCommissionSlab)
admin.site.register(SeasonTime)
admin.site.register(SightImage)
admin.site.register(ExperienceImage)




