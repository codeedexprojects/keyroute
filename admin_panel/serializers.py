from rest_framework import serializers
from admin_panel.models import Vendor
from .models import User
from vendors.serializers import *


class VendorSerializer1(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'


class AdminVendorSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(write_only=True)  # Admin needs to input mobile
    password = serializers.CharField(write_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = Vendor
        fields = [
            
            'user_id',
            'mobile', 'email_address', 'password', 'full_name',
            'travels_name', 'location', 'landmark', 'address',
            'city', 'state', 'pincode', 'district',
        ]

    def validate_mobile(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError('Mobile number must be at least 10 digits long.')
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError('Mobile number already registered.')
        return value

    def validate_email_address(self, value):  # validate the actual model field
        if value:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError('Email address already registered.')
            if Vendor.objects.filter(email_address=value).exists():
                raise serializers.ValidationError('Email address already registered with another vendor.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Password must be at least 6 characters long.')
        return value

    def create(self, validated_data):
        mobile = validated_data.pop('mobile', None)
        password = validated_data.pop('password', None)
        email = validated_data.get('email_address', None)  # pulling from vendor field directly

        if not mobile or not password:
            raise serializers.ValidationError('Mobile and Password are required.')

        user = User.objects.create_user(
            mobile=mobile,
            email=email,
            password=password,
            role=User.VENDOR
        )

        validated_data['user'] = user
        return Vendor.objects.create(**validated_data)



class VendorFullSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')
    buses = BusSerializer(source='bus_set', many=True, read_only=True)
    packages = PackageSerializer(source='package_set', many=True, read_only=True)

    bus_count = serializers.SerializerMethodField()
    package_count = serializers.SerializerMethodField()
    ongoing_buses = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'user_id',
            'email_address',
            'full_name',
            'travels_name',
            'location',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'district',
            'bus_count',
            'package_count',
            'buses',
            'ongoing_buses',
            'packages'
        ]

    def get_bus_count(self, obj):
        return obj.bus_set.count()

    def get_package_count(self, obj):
        return obj.package_set.count()

    def get_ongoing_buses(self, obj):
        ongoing_buses = obj.bus_set.all()[:2]  # dummy logic for ongoing buses
        return BusSerializer(ongoing_buses, many=True).data







# BUS DETAILS ADMIN SIDE
class BusImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusImage
        fields = ['id', 'bus_view_image']


class BusDetailSerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    bus_view_images = BusImageSerializer(source='busimage_set', many=True, read_only=True)

    class Meta:
        model = Bus
        fields = [
            'id',
            'bus_name', 'bus_number', 'bus_type', 'capacity', 'vehicle_description',
            'vehicle_rc_number', 'travels_logo', 'rc_certificate', 'license',
            'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance',
            'bus_view_images', 'amenities', 'base_price', 'price_per_km'
        ]



# ADMIN SIDE VENDOR PACKAGE LISING
class AdminPackageListSerializer(serializers.ModelSerializer):
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)

    class Meta:
        model = Package
        fields = [
            'id',
            'places',
            'days',
            'nights',
            'ac_available',
            'guide_included',
            'sub_category_name',
        ]




# ------------------------------- ADMIN SIDE VENDOR PACKAGE LISING SERIALISER-----------
class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['id', 'image']


class ActivitySerializer(serializers.ModelSerializer):
    images = ActivityImageSerializer(many=True, read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'name', 'description', 'images']


class MealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealImage
        fields = ['id', 'image']


class MealSerializer(serializers.ModelSerializer):
    images = MealImageSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = ['id', 'type', 'description', 'images']


class StayImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StayImage
        fields = ['id', 'image']


class StaySerializer(serializers.ModelSerializer):
    images = StayImageSerializer(many=True, read_only=True)

    class Meta:
        model = Stay
        fields = ['id', 'hotel_name', 'description', 'images']


class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ['id', 'image']


class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Place
        fields = ['id', 'name', 'description', 'images']


class DayPlanSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True, read_only=True)
    stay = StaySerializer(read_only=True)
    meals = MealSerializer(many=True, read_only=True)
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta:
        model = DayPlan
        fields = ['id', 'day_number', 'description', 'places', 'stay', 'meals', 'activities']


class AdminPackageDetailSerializer(serializers.ModelSerializer):
    sub_category = PackageSubCategorySerializer(read_only=True)
    day_plans = DayPlanSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category',
            'places',
            'days',
            'nights',
            'ac_available',
            'guide_included',
            'header_image',
            'day_plans',
            'created_at',
            'updated_at'
        ]

# -------------------------------- END---------------









class PackageCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageCategory
        fields = ['id', 'name', 'image']
