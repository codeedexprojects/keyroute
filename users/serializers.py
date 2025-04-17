import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite

from users.models import Review

User = get_user_model()

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['name', 'mobile', 'email', 'password', 'confirm_password']

    def validate(self, data):
        # Ensure passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Check if mobile number already exists
        if User.objects.filter(mobile=data['mobile']).exists():
            raise serializers.ValidationError({"mobile": "This mobile number is already registered."})

        # Ensure email is unique if provided
        if data.get('email'):
            if User.objects.filter(email=data['email']).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')  # Remove confirm_password before creating user
        
        user = User(
            name=validated_data.get('name', ''),
            mobile=validated_data['mobile'],
            email=validated_data.get('email', ''),
        )
        user.set_password(validated_data['password'])  # Hash password
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        mobile = data.get("mobile")
        password = data.get("password")

        if not mobile or not password:
            raise serializers.ValidationError("Mobile number and password are required.")

        user = authenticate(mobile=mobile, password=password)

        if not user:
            raise serializers.ValidationError("Invalid mobile number or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is not active.")

        data["user"] = user
        return data


class SendOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField()

    def validate_mobile(self, value):
        """Check if mobile number exists in the system"""
        if not User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError("User with this mobile number does not exist.")
        return value

    def send_otp(self):
        """Send OTP using external service"""
        mobile = self.validated_data['mobile']
        otp_api_key = "15b274f8-8600-11ef-8b17-0200cd936042"  # Your API key

        # Sample request to external OTP service (Modify as per provider)
        response = requests.post(
            "https://2factor.in/API/V1/{}/SMS/{}/AUTOGEN".format(otp_api_key, mobile)
        )
        print(response.json())

        if response.status_code == 200:
            return {"message": "OTP sent successfully."}
        else:
            raise serializers.ValidationError("Failed to send OTP. Try again later.")
        
class ResetPasswordSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    otp = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        """Ensure OTP is valid and passwords match"""
        mobile = data.get("mobile")
        otp = data.get("otp")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Verify OTP using external API
        otp_api_key = "15b274f8-8600-11ef-8b17-0200cd936042"
        response = requests.post(
            f"https://2factor.in/API/V1/{otp_api_key}/SMS/VERIFY3/{mobile}/{otp}"
        )

        if response.status_code != 200:
            raise serializers.ValidationError({"otp": "Invalid OTP or OTP expired."})

        return data

    def save(self):
        """Reset the user's password"""
        mobile = self.validated_data['mobile']
        new_password = self.validated_data['new_password']

        try:
            user = User.objects.get(mobile=mobile)
            user.set_password(new_password)
            user.save()
            return {"message": "Password reset successful."}
        except User.DoesNotExist:
            raise serializers.ValidationError({"mobile": "User not found."})


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def create(self, validated_data):
        user = self.context['request'].user
        return Review.objects.create(user=user, **validated_data)
    

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name', 'email', 'mobile']
        extra_kwargs = {
            'mobile': {'read_only': True},
            'email': {'required': False},
        }

    def validate_email(self, value):
        """Ensure email is unique if provided"""
        if value and User.objects.filter(email=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        """Update user profile"""
        instance.name = validated_data.get('name', instance.name)
        instance.email = validated_data.get('email', instance.email)
        instance.save()
        return instance

class FavouriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favourite
        fields = ['user', 'bus']

    def create(self, validated_data):
        user = validated_data.get('user')
        bus = validated_data.get('bus')

        favourite, created = Favourite.objects.get_or_create(user=user, bus=bus)
        return favourite