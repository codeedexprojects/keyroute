import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite
from admin_panel.utils import send_otp
from vendors.models import Bus, Package
from .models import UserWallet, ReferralTransaction

User = get_user_model()

class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['referral_code']

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
        fields = ['id', 'name', 'email', 'mobile', 'role','profile_image']
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


class UserWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWallet
        fields = ['balance']
        read_only_fields = ['balance']

class OngoingReferralSerializer(serializers.ModelSerializer):
    referred_user_name = serializers.SerializerMethodField()
    booking_details = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = ReferralTransaction
        fields = ['id', 'referred_user_name', 'booking_type', 'booking_id', 
                 'amount', 'status', 'date', 'booking_details']
        read_only_fields = fields

    def get_referred_user_name(self, obj):
        return obj.referred_user.name if hasattr(obj.referred_user, 'name') else str(obj.referred_user)
    
    def get_date(self, obj):
        return obj.created_at
    
    def get_booking_details(self, obj):
        if obj.booking_type == 'bus':
            try:
                from bookings.models import BusBooking
                booking = BusBooking.objects.get(id=obj.booking_id)
                return {
                    'from': booking.from_location,
                    'to': booking.to_location,
                    'date': booking.start_date
                }
            except:
                return {}
        elif obj.booking_type == 'package':
            try:
                from bookings.models import PackageBooking
                booking = PackageBooking.objects.get(id=obj.booking_id)
                return {
                    'package_name': booking.package.name if hasattr(booking.package, 'name') else "",
                    'date': booking.start_date
                }
            except:
                return {}
        return {}

class ReferralHistorySerializer(serializers.ModelSerializer):
    referred_user_name = serializers.SerializerMethodField()
    booking_details = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = ReferralTransaction
        fields = ['id', 'referred_user_name', 'booking_type', 'booking_id', 
                 'amount', 'transaction_type', 'date', 'booking_details']
        read_only_fields = fields

    def get_referred_user_name(self, obj):
        return obj.referred_user.name if hasattr(obj.referred_user, 'name') else str(obj.referred_user)
    
    def get_date(self, obj):
        return obj.completed_at or obj.created_at
    
    def get_booking_details(self, obj):
        if obj.booking_type == 'bus':
            try:
                from bookings.models import BusBooking
                booking = BusBooking.objects.get(id=obj.booking_id)
                return {
                    'from': booking.from_location,
                    'to': booking.to_location,
                    'date': booking.start_date
                }
            except:
                return {}
        elif obj.booking_type == 'package':
            try:
                from bookings.models import PackageBooking
                booking = PackageBooking.objects.get(id=obj.booking_id)
                return {
                    'package_name': booking.package.name if hasattr(booking.package, 'name') else "",
                    'date': booking.start_date
                }
            except:
                return {}
        return {}