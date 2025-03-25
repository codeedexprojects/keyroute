import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

from users.models import Review

User = get_user_model()

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)  # Optional email

    class Meta:
        model = User
        fields = ['phone_number', 'email', 'password', 'confirm_password']

    def validate(self, data):
        # Ensure passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Check if phone number already exists
        if User.objects.filter(phone_number=data['phone_number']).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')  # Remove confirm_password before creating user
        user = User(
            phone_number=validated_data['phone_number'],
            email=validated_data.get('email', '')  # Email is optional
        )
        user.set_password(validated_data['password'])  # Hash password
        user.save()
        return user




class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get("phone_number")
        password = data.get("password")

        if not phone_number or not password:
            raise serializers.ValidationError("Phone number and password are required.")

        user = authenticate(phone_number=phone_number, password=password)

        if not user:
            raise serializers.ValidationError("Invalid phone number or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is not active.")

        data["user"] = user
        return data




class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        """Check if phone number exists in the system"""
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("User with this phone number does not exist.")
        return value

    def send_otp(self):
        """Send OTP using external service"""
        phone_number = self.validated_data['phone_number']
        otp_api_key = "15b274f8-8600-11ef-8b17-0200cd936042"  # Your API key

        # Sample request to external OTP service (Modify as per provider)
        response = requests.post(
            "https://2factor.in/API/V1/{}/SMS/{}/AUTOGEN".format(otp_api_key, phone_number)
        )
        print(response.json())

        if response.status_code == 200:
            return {"message": "OTP sent successfully."}
        else:
            raise serializers.ValidationError("Failed to send OTP. Try again later.")
        
class ResetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        """Ensure OTP is valid and passwords match"""
        phone_number = data.get("phone_number")
        otp = data.get("otp")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Verify OTP using external API
        otp_api_key = "15b274f8-8600-11ef-8b17-0200cd936042"
        response = requests.post(
            f"https://2factor.in/API/V1/{otp_api_key}/SMS/VERIFY3/{phone_number}/{otp}"
        )

        if response.status_code != 200:
            raise serializers.ValidationError({"otp": "Invalid OTP or OTP expired."})

        return data

    def save(self):
        """Reset the user's password"""
        phone_number = self.validated_data['phone_number']
        new_password = self.validated_data['new_password']

        try:
            user = User.objects.get(phone_number=phone_number)
            user.set_password(new_password)
            user.save()
            return {"message": "Password reset successful."}
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone_number": "User not found."})


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def create(self, validated_data):
        user = self.context['request'].user  # Get the logged-in user
        return Review.objects.create(user=user, **validated_data)