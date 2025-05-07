import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite,Wallet
from admin_panel.utils import send_otp
from vendors.models import Bus, Package
from .models import ReferralRewardTransaction

User = get_user_model()

class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['referral_code']

class UserSignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    mobile = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    referral_code = serializers.CharField(max_length=10, required=False, allow_blank=True)

    def validate(self, data):
        if User.objects.filter(mobile=data['mobile']).exists():
            raise serializers.ValidationError({"mobile": "This mobile number is already registered."})

        if data.get('email') and User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "This email is already in use."})

        referral_code = data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                if data.get('mobile') == referrer.mobile:
                    raise serializers.ValidationError({"referral_code": "You cannot refer yourself."})
                data['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})
        
        return data

    def create(self, validated_data):
        referral_code = validated_data.pop('referral_code', None)
        referrer = validated_data.pop('referrer', None)

        user = User(
            name=validated_data.get('name', ''),
            mobile=validated_data['mobile'],
            email=validated_data.get('email', ''),
        )
        user.set_unusable_password()
        user.save()

        Wallet.objects.create(
            user=user,
            referred_by=referrer
        )

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
        fields = ['id', 'name', 'email', 'mobile', 'role', 'referral_code', 'profile_image']
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

        if 'profile_image' in validated_data:
            instance.profile_image = validated_data.get('profile_image')

        instance.save()
        return instance

# class ReviewSerializer(serializers.ModelSerializer):
#     user_name = serializers.SerializerMethodField(read_only=True)
    
#     class Meta:
#         model = Review
#         fields = ['id', 'user', 'rating', 'comment', 'created_at', 'user_name']
#         read_only_fields = ['id', 'created_at', 'user_name']
#         extra_kwargs = {
#             'user': {'write_only': True, 'required': False},
#         }
        
#     def get_user_name(self, obj):
#         return obj.user.name if obj.user.name else obj.user.mobile
    
#     def create(self, validated_data):
#         user = self.context['request'].user
#         validated_data['user'] = user
#         return Review.objects.create(**validated_data)

class FavouriteSerializer(serializers.ModelSerializer):
    bus_details = serializers.SerializerMethodField(read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Favourite
        fields = ['id', 'user', 'bus', 'package', 'bus_details', 'package_details']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
        }

    def get_bus_details(self, obj):
        if obj.bus:
            from vendors.serializers import BusSerializer
            return BusSerializer(obj.bus).data
        return None
        
    def get_package_details(self, obj):
        if obj.package:
            from vendors.serializers import PackageSerializer
            return PackageSerializer(obj.package).data
        return None

    def create(self, validated_data):
        user = self.context['request'].user if 'request' in self.context else validated_data.get('user')
        if not user and 'user' not in validated_data:
            raise serializers.ValidationError("User is required")
            
        validated_data['user'] = user
        bus = validated_data.get('bus')
        package = validated_data.get('package')

        if bus and package:
            raise serializers.ValidationError("Cannot favorite both bus and package at the same time")
            
        if not bus and not package:
            raise serializers.ValidationError("Either bus or package must be provided")

        if bus:
            favourite, created = Favourite.objects.get_or_create(user=user, bus=bus)
        else:
            favourite, created = Favourite.objects.get_or_create(user=user, package=package)
        return favourite
    
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['balance', 'referred_by', 'referral_used']


class OngoingReferralSerializer(serializers.ModelSerializer):
    referred_user_name = serializers.CharField(source='referred_user.name', read_only=True)
    booking_type_display = serializers.CharField(source='get_booking_type_display', read_only=True)
    created_at = serializers.DateTimeField(format="%d %b %Y", read_only=True)
    
    class Meta:
        model = ReferralRewardTransaction
        fields = [
            'id', 
            'referred_user_name', 
            'booking_type', 
            'booking_type_display',
            'booking_id', 
            'reward_amount', 
            'status',
            'created_at'
        ]

class ReferralHistorySerializer(serializers.ModelSerializer):
    referred_user_name = serializers.CharField(source='referred_user.name', read_only=True)
    booking_type_display = serializers.CharField(source='get_booking_type_display', read_only=True)
    created_at = serializers.DateTimeField(format="%d %b %Y", read_only=True)
    credited_at = serializers.DateTimeField(format="%d %b %Y", read_only=True)
    
    class Meta:
        model = ReferralRewardTransaction
        fields = [
            'id', 
            'referred_user_name', 
            'booking_type', 
            'booking_type_display',
            'booking_id', 
            'reward_amount', 
            'status',
            'created_at',
            'credited_at'
        ]
