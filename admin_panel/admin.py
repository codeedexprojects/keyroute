from django.contrib import admin
from .models import *
from users.models import *
# Register your models here.

admin.site.register(Vendor)
admin.site.register(Advertisement)
admin.site.register(Experience)
admin.site.register(Sight)
admin.site.register(LimitedDeal)
admin.site.register(FooterSection)
admin.site.register(LimitedDealImage)
admin.site.register(AdminCommission)

admin.site.register(AdminCommissionSlab)

@admin.register(OTPSession)
class OTPSessionAdmin(admin.ModelAdmin):
    list_display = ('mobile', 'session_id', 'is_new_user', 'created_at', 'expires_at', 'is_expired')
    search_fields = ('mobile', 'session_id')
    list_filter = ('is_new_user',)
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = "Expired"

# Register your existing admin models here
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'email', 'role', 'referral_code', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('name', 'mobile', 'email', 'referral_code')
    
admin.site.register(SeasonTime)
admin.site.register(SightImage)
admin.site.register(ExperienceImage)
admin.site.register(ReferAndEarn)
admin.site.register(FooterImage)




