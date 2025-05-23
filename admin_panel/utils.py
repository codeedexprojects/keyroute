import requests
import string
import random


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

def generate_referral_code(length=7):
    """
    Generate a unique referral code
    """
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))



def get_admin_commission_from_db(total_amount):
    from .models import AdminCommissionSlab
    slab = AdminCommissionSlab.objects.filter(
        min_amount__lte=total_amount,
        max_amount__gte=total_amount
    ).first()

    if slab:
        revenue = round(total_amount * (slab.commission_percentage / 100), 2)
        return slab.commission_percentage, revenue

    return 0, 0


def get_advance_amount_from_db(advance_amount):
    from .models import AdminCommissionSlab
    slab = AdminCommissionSlab.objects.filter(
        min_amount__lte=advance_amount,
        max_amount__gte=advance_amount
    ).first()

    if slab:
        advance = round(advance_amount * (slab.advance_percentage / 100), 2)
        return slab.advance_percentage, advance

    return 0, 0
