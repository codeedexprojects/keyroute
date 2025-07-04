import requests
import string
import random
import re


API_KEY = "4657d099-5270-11f0-a562-0200cd936042"
TEMPLATE_NAME = "Keyroute OTP Verification"  # exact match, case-sensitive

def is_valid_email(value):
    return re.match(r"[^@]+@[^@]+\.[^@]+", value)

def generate_otp():
    """Generate a 6-digit numeric OTP"""
    return str(random.randint(100000, 999999))

def send_otp(mobile, username="User", otp=None):
    """Send OTP to mobile using 2Factor's DLT template-based SMS"""
    if otp is None:
        otp = generate_otp()

    # Template name must be URL-encoded (space becomes %20)
    encoded_template = TEMPLATE_NAME.replace(" ", "%20")
    url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{mobile}/AUTOGEN/{encoded_template}/{username}/{otp}"

    response = requests.get(url)

    try:
        return response.json()
    except Exception:
        raise Exception(f"Failed to parse response. Status {response.status_code}, Response: {response.text}")



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
        # Calculate commission from total_amount
        revenue = round(total_amount * (slab.commission_percentage / 100), 2)
        return slab.commission_percentage, revenue

    return 0, 0


def get_advance_amount_from_db(total_amount):  # Changed parameter name for clarity
    from .models import AdminCommissionSlab
    slab = AdminCommissionSlab.objects.filter(
        min_amount__lte=total_amount,
        max_amount__gte=total_amount
    ).first()

    if slab:
        # Calculate advance amount from total_amount
        advance = round(total_amount * (slab.advance_percentage / 100), 2)
        return slab.advance_percentage, advance

    return 0, 0
