from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from admin_panel.models import Vendor, User
from .models import *
from django.core.exceptions import ValidationError

class VendorSerializer(serializers.ModelSerializer):

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Vendor
        fields = [
            'username', 'password', 'full_name', 'email_address', 'phone_no', 
            'travels_name', 'location', 'landmark', 'address', 
            'city', 'state', 'pincode'
        ]

    def validate_username(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Username must be at least 5 characters long.')
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email_address(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Email address must be at least 5 characters long.')
        if Vendor.objects.filter(email_address=value).exists():
            raise serializers.ValidationError('Email address already exists.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Password must be at least 5 characters long.')
        return value

    
    
    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            role=User.VENDOR,
            password=make_password(validated_data['password'])
        )
        validated_data.pop('username', None)
        validated_data.pop('password', None)
        validated_data['user'] = user

        vendor = Vendor.objects.create(**validated_data)   
        return vendor



class BusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = [
            'id',
            'bus_name', 'bus_number', 'bus_type', 'capacity', 'vehicle_description',
            'vehicle_rc_number', 'travels_logo', 'rc_certificate', 'license',
            'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance', 'bus_view_images'
        ]

    bus_view_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True
    )

    def validate_bus_number(self, value):
        if Bus.objects.filter(bus_number=value).exists():
            raise serializers.ValidationError("A bus with this number already exists.")
        return value

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be a positive number.")
        return value

    def validate_vehicle_rc_number(self, value):
        if not value.isalnum():
            raise serializers.ValidationError("RC number must be alphanumeric.")
        return value

    def create(self, validated_data):
        bus_images = validated_data.pop('bus_view_images', [])

        vendor = self.context['vendor']

        bus = Bus.objects.create(vendor=vendor, **validated_data)

        for image in bus_images:
            BusImage.objects.create(bus=bus, bus_view_image=image)

        return bus
    





class PackageCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageCategory
        fields = ['id', 'vendor', 'name', 'image']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Category name cannot be empty.")
        return value



class PackageSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageSubCategory
        fields = ['id',  'category', 'name', 'image']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("SubCategory name cannot be empty.")
        return value


def validate_days_nights(days, nights):
    if days < 0 or nights < 0:
        raise ValidationError("Days and nights must be non-negative numbers.")

def validate_places(places):
    if not places.strip():
        raise ValidationError("Places field cannot be empty.")





class PackageSerializer(serializers.ModelSerializer):
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    class Meta:
        model = Package
        fields = ['id', 'vendor', 'sub_category', 'places', 'days', 'nights', 'ac_available', 'guide_included', 'buses', 'header_image', 'created_at', 'updated_at']

    def validate(self, data):
        validate_days_nights(data.get('days', 0), data.get('nights', 0))
        validate_places(data.get('places', ''))
        return data
    
    def validate_buses(self, value):
        bus_ids = [bus.id for bus in value]  
        existing_bus_ids = set(Bus.objects.filter(id__in=bus_ids).values_list('id', flat=True))

        missing_ids = set(bus_ids) - existing_bus_ids
        if missing_ids:
            raise serializers.ValidationError(f"Invalid bus IDs: {list(missing_ids)}")
        return value




