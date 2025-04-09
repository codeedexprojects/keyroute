from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from admin_panel.models import Vendor, User
from .models import *
from django.db import transaction
from django.core.exceptions import ValidationError


class VendorSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True, required=False)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Vendor
        fields = [
            'mobile', 'email', 'password', 'full_name',  
            'travels_name', 'location', 'landmark', 'address', 
            'city', 'state', 'pincode'
        ]

    def validate_mobile(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError('Mobile number must be at least 10 digits long.')
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError('Mobile number already registered.')
        return value

   

    def validate_email(self, value):
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
        mobile = validated_data.pop('mobile')
        email = validated_data.pop('email', None)   
        password = validated_data.pop('password')

        user = User.objects.create_user(
            mobile=mobile,
            email=email if email else None,  
            password=password,
            role=User.VENDOR
        )

        validated_data['user'] = user
        validated_data['email_address'] = email if email else None   
        vendor = Vendor.objects.create(**validated_data)
        return vendor










class BusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = [
            'id',
            'bus_name', 'bus_number', 'bus_type', 'capacity', 'vehicle_description',
            'vehicle_rc_number', 'travels_logo', 'rc_certificate', 'license',
            'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance', 'bus_view_images','amenities','base_price', 'price_per_km' 
        ]

    bus_view_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True
    )
    amenities = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(),
        many=True,
        required=False
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
        amenities = validated_data.pop('amenities', [])
        vendor = self.context['vendor']

        bus = Bus.objects.create(vendor=vendor, **validated_data)

        for image in bus_images:
            BusImage.objects.create(bus=bus, bus_view_image=image)

        bus.amenities.set(amenities)
        return bus

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name']


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
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)  
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)  
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)

    class Meta:
        model = Package
        fields = [
            'id', 'vendor', 'vendor_name', 'sub_category', 'sub_category_name', 
            'places', 'days', 'nights', 'ac_available', 'guide_included', 
            'buses', 'header_image', 'created_at', 'updated_at'
        ]

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











class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ['image']

class StayImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StayImage
        fields = ['image']

class MealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealImage
        fields = ['image']

class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['image']

class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, write_only=True)

    class Meta:
        model = Place
        fields = ['name', 'description', 'images']

class StaySerializer(serializers.ModelSerializer):
    images = StayImageSerializer(many=True, write_only=True)

    class Meta:
        model = Stay
        fields = ['hotel_name', 'description', 'images']

class MealSerializer(serializers.ModelSerializer):
    images = MealImageSerializer(many=True, write_only=True)

    class Meta:
        model = Meal
        fields = ['type', 'description', 'images']

class ActivitySerializer(serializers.ModelSerializer):
    images = ActivityImageSerializer(many=True, write_only=True)

    class Meta:
        model = Activity
        fields = ['name', 'description', 'images']

class DayPlanSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True)
    stay = StaySerializer()
    meals = MealSerializer(many=True)
    activities = ActivitySerializer(many=True)

    class Meta:
        model = DayPlan
        fields = ['day_number', 'places', 'stay', 'meals', 'activities']

class PackageSerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, write_only=True)

    class Meta:
        model = Package
        fields = [
            'sub_category', 'header_image', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'buses', 
            'day_plans'
        ]

    def validate_days(self, value):
        if value <= 0:
            raise serializers.ValidationError("Days must be greater than 0.")
        return value

    def validate_nights(self, value):
        if value < 0:
            raise serializers.ValidationError("Nights cannot be negative.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        vendor = self.context['vendor']
        day_plans_data = validated_data.pop('day_plans')
        package = Package.objects.create(vendor=vendor, **validated_data)

        for day_data in day_plans_data:
            places_data = day_data.pop('places')
            stay_data = day_data.pop('stay')
            meals_data = day_data.pop('meals')
            activities_data = day_data.pop('activities')

            day_plan = DayPlan.objects.create(package=package, **day_data)

            for place in places_data:
                images = place.pop('images')
                place_instance = Place.objects.create(day_plan=day_plan, **place)
                for image in images:
                    PlaceImage.objects.create(place=place_instance, image=image['image'])

            stay_images = stay_data.pop('images')
            stay_instance = Stay.objects.create(day_plan=day_plan, **stay_data)
            for image in stay_images:
                StayImage.objects.create(stay=stay_instance, image=image['image'])

            for meal in meals_data:
                images = meal.pop('images')
                meal_instance = Meal.objects.create(day_plan=day_plan, **meal)
                for image in images:
                    MealImage.objects.create(meal=meal_instance, image=image['image'])

            for activity in activities_data:
                images = activity.pop('images')
                activity_instance = Activity.objects.create(day_plan=day_plan, **activity)
                for image in images:
                    ActivityImage.objects.create(activity=activity_instance, image=image['image'])

        return package







