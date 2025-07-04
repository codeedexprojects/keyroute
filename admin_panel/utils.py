import requests
import string
import random
import re



API_KEY = "4657d099-5270-11f0-a562-0200cd936042"

def is_valid_email(value):
    return re.match(r"[^@]+@[^@]+\.[^@]+", value)

def send_otp(mobile, name):
    """
    Sends OTP to the given mobile number using 2Factor API with custom message.
    """
    # For custom message, use transactional SMS endpoint
    message = f"Dear {name}, your OTP for verification on KEYROUTE EXPEDO PVT LTD is {{OTP}} Do not share this with anyone. It is valid for 5 minutes. Visit keyrouteexpedo.com for more info."
    
    url = f"https://2factor.in/API/V1/{API_KEY}/ADDON_SERVICES/SEND/TSMS"
    params = {
        'From': 'KEYROUTE',
        'To': mobile,
        'Msg': message.replace('{OTP}', 'AUTOGEN')  # You'll need to generate OTP separately
    }
    
    response = requests.get(url, params=params)
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
