import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite
from admin_panel.utils import send_otp
from users.models import Review

User = get_user_model()

class UserSignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    mobile = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    
    def validate(self, data):
        if User.objects.filter(mobile=data['mobile']).exists():
            raise serializers.ValidationError({"mobile": "This mobile number is already registered."})

        if data.get('email') and data['email']:
            if User.objects.filter(email=data['email']).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})

        return data

    def create(self, validated_data):
        user = User(
            name=validated_data.get('name', ''),
            mobile=validated_data['mobile'],
            email=validated_data.get('email', ''),
        )
        user.set_unusable_password()
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(help_text="Mobile number")

    def validate(self, data):
        mobile = data.get("mobile")

        if not mobile:
            raise serializers.ValidationError("Mobile number is required.")

        user = User.objects.filter(mobile=mobile).first()

        if not user:
            raise serializers.ValidationError("User not found with this mobile/email.")

        if not user.is_active:
            raise serializers.ValidationError("User account is not active.")

        data["user"] = user
        data["mobile"] = user.mobile  # For OTP sending
        return data


class SendOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField()

    def validate_mobile(self, value):
        if not User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError("User with this mobile number does not exist.")
        return value

    def send_otp(self):
        mobile = self.validated_data['mobile']
        
        response = send_otp(mobile)

        if response.get("Status") == "Success":
            return {
                "message": "OTP sent successfully.",
                "session_id": response.get("Details")
            }
        else:
            raise serializers.ValidationError("Failed to send OTP. Try again later.")
        
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'mobile', 'role']
        extra_kwargs = {
            'mobile': {'read_only': True},
            'email': {'required': False},
            'role': {'read_only': True},
            'id': {'read_only': True},
        }

    def validate_email(self, value):
        if value == "":
            return None
            
        if value and User.objects.filter(email=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        
        if 'email' in validated_data:
            instance.email = validated_data.get('email')
            
        instance.save()
        return instance

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def create(self, validated_data):
        user = self.context['request'].user
        return Review.objects.create(user=user, **validated_data)
    

class FavouriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favourite
        fields = ['user', 'bus','package']

    def create(self, validated_data):
        user = validated_data.get('user')
        bus = validated_data.get('bus')
        package = validated_data.get('package')

        if bus:
            favourite, created = Favourite.objects.get_or_create(user=user, bus=bus)
        else:
            favourite, created = Favourite.objects.get_or_create(user=user, package=package)
        return favourite