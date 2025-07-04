import requests
import string
import random
import re




API_KEY = "4657d099-5270-11f0-a562-0200cd936042"
TEMPLATE_NAME = "Keyroute OTP Verification"  # Must match your DLT template exactly

def is_valid_email(value):
    return re.match(r"[^@]+@[^@]+\.[^@]+", value)

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(mobile):
    otp = generate_otp()

    # Ensure country code is included
    if not mobile.startswith("91"):
        mobile = "91" + mobile

    # Use the template-based SMS API
    url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{mobile}/{otp}/{TEMPLATE_NAME}"

    # Recommended headers
    headers = {
        "User-Agent": "axios/0.27.2",
        "Accept": "application/json, text/plain, */*"
    }

    response = requests.get(url, headers=headers)

    try:
        data = response.json()
    except ValueError:
        return {
            "status": "failed",
            "raw_response": response.text
        }

    if response.status_code == 200 and data.get("Status") == "Success":
        return {
            "status": "success",
            "otp": otp,
            "response": data
        }
    else:
        return {
            "status": "failed",
            "reason": data.get("Details") or data.get("error"),
            "response": data
        }


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
