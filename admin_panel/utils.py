import requests


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
