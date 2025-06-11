from django.contrib import admin
from .models import BusBooking,PackageBooking,Travelers,BusDriverDetail,PackageDriverDetail,UserBusSearch,WalletTransaction

# Register your models here.
admin.site.register(BusBooking)
admin.site.register(PackageBooking)
admin.site.register(Travelers)
admin.site.register(BusDriverDetail)
admin.site.register(PackageDriverDetail)
admin.site.register(UserBusSearch)

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'booking_id', 'booking_type', 'transaction_type', 'amount', 'balance_after', 'created_at', 'is_active']
    list_filter = ['transaction_type', 'booking_type', 'is_active', 'created_at']
    search_fields = ['user__username', 'booking_id', 'reference_id']
    readonly_fields = ['created_at', 'balance_before', 'balance_after']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('user', 'booking_id', 'booking_type', 'transaction_type', 'amount')
        }),
        ('Balance Info', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Additional Info', {
            'fields': ('description', 'reference_id', 'is_active', 'created_at')
        }),
    )