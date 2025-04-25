import requests
from .models import AdminCommissionSlab


API_KEY = "15b274f8-8600-11ef-8b17-0200cd936042"

def send_otp(mobile):
    """
    Sends OTP to the given mobile number using 2Factor API.
    """
    url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{mobile}/AUTOGEN"
    response = requests.get(url)
    return response.json()

def verify_otp(mobile, otp):
    """
    Verifies OTP for the given mobile number using 2Factor API.
    """
    url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY3/{mobile}/{otp}"
    response = requests.get(url)
    return response.json()





def get_admin_commission_from_db(trip_amount):
    slab = AdminCommissionSlab.objects.filter(
        min_amount__lte=trip_amount,
        max_amount__gte=trip_amount
    ).first()

    if slab:
        revenue = round(trip_amount * (slab.commission_percentage / 100), 2)
        return slab.commission_percentage, revenue

    return 0, 0
