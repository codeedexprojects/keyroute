from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from admin_panel.models import Vendor, User
from .models import *
from django.db import transaction
from django.core.exceptions import ValidationError
import re
from bookings.models import *
import json
from users.models import Favourite
from bookings.models import *


class VendorSerializer(serializers.ModelSerializer):

    phone_number = serializers.CharField(source='user.mobile', read_only=True)
    mobile = serializers.CharField(write_only=True) 
    password = serializers.CharField(write_only=True)
    # profile_image = serializers.SerializerMethodField()
    profile_image = serializers.ImageField(source='user.profile_image', allow_null=True, required=False)

    class Meta:
        model = Vendor
        fields = [
            'mobile', 'email_address', 'password', 'full_name',  
            'travels_name', 'location', 'landmark', 'address', 
            'city', 'state', 'pincode','district','profile_image','phone_number'
        ]

    def validate_mobile(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError('Mobile number must be at least 10 digits long.')
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError('Mobile number already registered.')
        return value

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.user.profile_image:
            image_url = obj.user.profile_image.url
            if request is not None:
                return request.build_absolute_uri(image_url)
            return image_url
        return None
    

   

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
        # email = validated_data.pop('email', None) 
        email = validated_data.get('email_address') or None  
        password = validated_data.pop('password')
        profile_image = validated_data.pop('user', {}).get('profile_image', None)

        

        user = User.objects.create_user(
            mobile=mobile,
            email=email if email else None,  
            password=password,
            role=User.VENDOR
        )
        if profile_image:
            user.profile_image = profile_image
            user.save()
        

        validated_data['user'] = user
        validated_data['email_address'] = email if email else None   
        vendor = Vendor.objects.create(**validated_data)
        return vendor

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        profile_image = user_data.get('profile_image', None)

        if profile_image:
            instance.user.profile_image = profile_image
            instance.user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class VendorUpdateSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(source='user.mobile', required=False)
    profile_image = serializers.ImageField(source='user.profile_image', required=False)


    class Meta:
        model = Vendor
        fields = [
            "full_name", "email_address", "travels_name", "location", "landmark",
            "address", "city", "state", "pincode", "district", "mobile","profile_image"
        ]



    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        return instance     


 

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = '__all__'

    def validate(self, data):
        if data.get('days', 0) + data.get('nights', 0) <= 0:
            raise serializers.ValidationError("Total duration (days + nights) must be greater than zero.")
        return data



class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name','icon']




# ----------------------------------- list bus----------------------


class BusSummarySerializer(serializers.ModelSerializer):
    amenities_count = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    bus_travel_image = serializers.SerializerMethodField()  

    class Meta:
        model = Bus
        fields = ['id',
            'bus_name',
            'bus_number',
            'features',
            'capacity',
            'amenities_count',
            'base_price',
            'price_per_km',
            'bus_travel_image'   
        ]
    
    def get_features(self, obj):
        return [feature.name for feature in obj.features.all()]

    def get_amenities_count(self, obj):
        amenities_count = obj.amenities.count()
        return f"{amenities_count}+" if amenities_count >= 5 else str(amenities_count)

    def get_total_capacity(self, obj):
        return obj.capacity

    def get_bus_travel_image(self, obj):
        bus_travel_image = BusTravelImage.objects.filter(bus=obj).first()
        if bus_travel_image and bus_travel_image.image:
            return bus_travel_image.image.url   
        return None  















# -----------------------


class BusSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()
    amenities = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    bus_view_images = serializers.SerializerMethodField()  # Changed to SerializerMethodField for reading
    bus_travel_images = serializers.SerializerMethodField()  # Changed to SerializerMethodField for reading
    
    # Separate write-only fields for creating/updating images
    bus_view_images_upload = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    bus_travel_images_upload = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()

    class Meta:
        model = Bus
        fields = [
            'id','average_rating', 'total_reviews', 'features', 'minimum_fare', 'bus_travel_images', 'bus_name', 'bus_number',
            'capacity', 'vehicle_description', 'travels_logo',
            'rc_certificate', 'license', 'contract_carriage_permit', 'passenger_insurance',
            'vehicle_insurance', 'bus_view_images', 'amenities', 'base_price', 'price_per_km','location','is_favorite','bus_type','longitude','latitude','base_price_km','is_popular',
            'bus_view_images_upload', 'bus_travel_images_upload','night_allowance'
        ]

    def get_features(self, obj):
        return BusFeatureSerializer(obj.features.all(), many=True).data
    
    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, bus=obj).exists()
        return False

    def get_amenities(self, obj):
        return AmenitySerializer(obj.amenities.all(), many=True).data

    def get_bus_view_images(self, obj):
        """Return list of bus view image URLs"""
        request = self.context.get('request')
        images = obj.images.all()  # Using related_name='images' from BusImage model
        if request:
            return [request.build_absolute_uri(image.bus_view_image.url) for image in images if image.bus_view_image]
        return [image.bus_view_image.url for image in images if image.bus_view_image]

    def get_bus_travel_images(self, obj):
        """Return list of bus travel image URLs"""
        request = self.context.get('request')
        images = obj.travel_images.all()  # Using related_name='travel_images' from BusTravelImage model
        if request:
            return [request.build_absolute_uri(image.image.url) for image in images if image.image]
        return [image.image.url for image in images if image.image]

    def validate_bus_number(self, value):
        # Fixed validation to exclude current instance during updates
        instance = getattr(self, 'instance', None)
        queryset = Bus.objects.filter(bus_number=value)
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A bus with this number already exists.")
        return value

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be a positive number.")
        return value

    def create(self, validated_data):
        # Fixed: Use get() with default empty list to avoid KeyError
        bus_images = validated_data.pop('bus_view_images_upload', [])
        travel_images = validated_data.pop('bus_travel_images_upload', [])
        amenities = validated_data.pop('amenities', [])
        features = validated_data.pop('features', [])
        
        vendor = self.context['vendor']

        bus = Bus.objects.create(vendor=vendor, **validated_data)

        # Create bus view images
        for image in bus_images:
            BusImage.objects.create(bus=bus, bus_view_image=image)

        # Create bus travel images
        for travel_img in travel_images:
            BusTravelImage.objects.create(bus=bus, image=travel_img)

        # Set many-to-many relationships
        bus.amenities.set(amenities)
        bus.features.set(features)
        
        return bus

    def update(self, instance, validated_data):
        # Handle image updates
        bus_images = validated_data.pop('bus_view_images_upload', None)
        travel_images = validated_data.pop('bus_travel_images_upload', None)
        amenities = validated_data.pop('amenities', None)
        features = validated_data.pop('features', None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update bus view images if provided
        if bus_images is not None:
            # Clear existing images and add new ones
            instance.images.all().delete()  # Using related_name='images'
            for image in bus_images:
                BusImage.objects.create(bus=instance, bus_view_image=image)

        # Update bus travel images if provided
        if travel_images is not None:
            # Clear existing images and add new ones
            instance.travel_images.all().delete()  # Using related_name='travel_images'
            for travel_img in travel_images:
                BusTravelImage.objects.create(bus=instance, image=travel_img)

        # Update many-to-many relationships if provided
        if amenities is not None:
            instance.amenities.set(amenities)
        if features is not None:
            instance.features.set(features)

        return instance


# commented for rabeeh


# class BusSerializer(serializers.ModelSerializer):
#     features = serializers.SerializerMethodField()
#     amenities = serializers.SerializerMethodField()
#     is_favorite = serializers.SerializerMethodField()
#     bus_view_images = serializers.ListField(
#         child=serializers.ImageField(),
#         write_only=True
#     )

#     bus_travel_images = serializers.ListField(
#         child=serializers.ImageField(),
#         write_only=True,
#         required=False
#     )

#     average_rating = serializers.ReadOnlyField()
#     total_reviews = serializers.ReadOnlyField()

#     class Meta:
#         model = Bus
#         fields = [
#             'id','average_rating', 'total_reviews', 'features', 'minimum_fare', 'bus_travel_images', 'bus_name', 'bus_number',
#             'capacity', 'vehicle_description', 'travels_logo',
#             'rc_certificate', 'license', 'contract_carriage_permit', 'passenger_insurance',
#             'vehicle_insurance', 'bus_view_images', 'amenities', 'base_price', 'price_per_km','location','is_favorite','bus_type','longitude','latitude','base_price_km','is_popular'
#         ]

#     def get_features(self, obj):
#         return BusFeatureSerializer(obj.features.all(), many=True).data
    
#     def get_is_favorite(self, obj):
#         request = self.context.get('request')
#         if request and request.user.is_authenticated:
#             return Favourite.objects.filter(user=request.user, bus=obj).exists()
#         return False

#     def get_amenities(self, obj):
#         return AmenitySerializer(obj.amenities.all(), many=True).data

#     def validate_bus_number(self, value):
#         if Bus.objects.filter(bus_number=value).exists():
#             raise serializers.ValidationError("A bus with this number already exists.")
#         return value

#     def validate_capacity(self, value):
#         if value <= 0:
#             raise serializers.ValidationError("Capacity must be a positive number.")
#         return value


    
#     def create(self, validated_data):
#         bus_images = validated_data.pop('bus_view_images', [])
#         amenities = validated_data.pop('amenities', [])
        
#         features = validated_data.pop('features', [])
#         vendor = self.context['vendor']
#         travel_images = validated_data.pop('bus_travel_images', [])

#         bus = Bus.objects.create(vendor=vendor, **validated_data)

#         for image in bus_images:
#             BusImage.objects.create(bus=bus, bus_view_image=image)

#         for travel_img in travel_images:
#             BusTravelImage.objects.create(bus=bus, image=travel_img)

#         bus.amenities.set(amenities)
#         bus.features.set(features) 
#         return bus


# here it end


# class BusSerializer(serializers.ModelSerializer):


#     features = serializers.PrimaryKeyRelatedField(
#         queryset=BusFeature.objects.all(), many=True, required=False
#     )
    
#     amenities = serializers.PrimaryKeyRelatedField(
#         queryset=Amenity.objects.all(),
#         many=True,
#         required=False
#     )

#     # amenities = AmenitySerializer(many=True, read_only=True)
#     def to_representation(self, instance):
#         rep = super().to_representation(instance)
#         rep['amenities'] = AmenitySerializer(instance.amenities.all(), many=True).data
#         return rep

    
#     class Meta:
#         model = Bus
#         fields = [
#             'id',
#             'features',
#             'id',
#             'features',
#             'minimum_fare',
#             'bus_travel_images',

#             'bus_name', 'bus_number',  'capacity', 'vehicle_description',
#             'travels_logo', 'rc_certificate', 'license',
#             'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance', 'bus_view_images','amenities','base_price', 'price_per_km' 
#         ]

    

#     bus_view_images = serializers.ListField(
#         child=serializers.ImageField(),
#         write_only=True
#     )

#     bus_travel_images = serializers.ListField(
#     child=serializers.ImageField(),
#     write_only=True,
#     required=False
#     )


  
#     def get_amenities(self, obj):
#         return [amenity.name for amenity in obj.amenities.all()]
  
#     def validate_bus_number(self, value):
#         if Bus.objects.filter(bus_number=value).exists():
#             raise serializers.ValidationError("A bus with this number already exists.")
#         return value

#     def validate_capacity(self, value):
#         if value <= 0:
#             raise serializers.ValidationError("Capacity must be a positive number.")
#         return value
    
  
  

    
#     def create(self, validated_data):
#         bus_images = validated_data.pop('bus_view_images', [])
#         amenities = validated_data.pop('amenities', [])
        
#         features = validated_data.pop('features', [])
#         vendor = self.context['vendor']
#         travel_images = validated_data.pop('bus_travel_images', [])

#         bus = Bus.objects.create(vendor=vendor, **validated_data)

#         for image in bus_images:
#             BusImage.objects.create(bus=bus, bus_view_image=image)

#         for travel_img in travel_images:
#             BusTravelImage.objects.create(bus=bus, image=travel_img)

#         bus.amenities.set(amenities)
#         bus.features.set(features) 
#         return bus














class PackageCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageCategory
        fields = ['id', 'name', 'image']

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


# def validate_days_nights(days, nights):
#     if days < 0 or nights < 0:
#         raise ValidationError("Days and nights must be non-negative numbers.")

# def validate_places(places):
#     if not places.strip():
#         raise ValidationError("Places field cannot be empty.")



class PackageImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageImage
        fields = ['image']






# SAMPLE
class PackageSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)  
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)  
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    package_images = PackageImageSerializer(many=True, write_only=True)

    class Meta:
        model = Package
        fields = [
            'id', 'vendor', 'vendor_name', 'sub_category', 'sub_category_name', 
            'places', 'days', 'ac_available', 'guide_included', 
            'buses', 'header_image', 'created_at', 'updated_at',
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
        fields = ['day_number', 'places', 'stay', 'meals', 'activities','description']

class PackageSerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, write_only=True)
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    travels_name = serializers.SerializerMethodField()
    travels_location = serializers.SerializerMethodField()
    day_plans_read = DayPlanSerializer(source='dayplan_set', many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    price_per_person = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category', 'header_image', 'places', 'days',
            'ac_available', 'guide_included', 'buses', 
            'day_plans','day_plans_read','average_rating', 'total_reviews','price_per_person','is_favorite','travels_name','travels_location'
        ]
    
    def get_travels_name(self, obj):
        return obj.vendor.travels_name
    
    def get_travels_location(self, obj):
        return obj.vendor.location

    def get_price_per_person(self, obj):
        if obj.price_per_person is not None:
            return int(obj.price_per_person)
        return 0
    
    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, package=obj).exists()
        return False
    
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
        buses_data = validated_data.pop('buses') 
        print(buses_data,'bjuuuu')
        package = Package.objects.create(vendor=vendor, **validated_data)
        package.buses.set(buses_data)

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



class PackageBasicSerializer(serializers.ModelSerializer):
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    package_images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    bus_location = serializers.CharField(required=False, allow_blank=True)
    price_per_person = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    extra_charge_per_km = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)



    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category', 'header_image', 'places', 'days',
            'ac_available', 'guide_included', 'buses', 'package_images','bus_location', 'price_per_person','extra_charge_per_km'
        ]

    def create(self, validated_data):
        vendor = self.context['vendor']
        buses = validated_data.pop('buses')
        images = validated_data.pop('package_images', [])

        package = Package.objects.create(vendor=vendor, **validated_data)
        package.buses.set(buses)

        for img in images:
            PackageImage.objects.create(package=package, image=img)

        return package































# ------------------------------------------- PACKAGE EDITING SECTION----------
class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ['id', 'image']

class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Place
        fields = ['id', 'name', 'description', 'images']


class StayImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StayImage
        fields = ['id', 'image']

class StaySerializer(serializers.ModelSerializer):
    images = StayImageSerializer(many=True, read_only=True)

    class Meta:
        model = Stay
        fields = ['id', 'hotel_name', 'description', 'images','has_breakfast','is_ac','location']


class MealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealImage
        fields = ['id', 'image']

class MealSerializer(serializers.ModelSerializer):
    images = MealImageSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = ['id', 'type', 'description', 'images','time','location','restaurant_name']


class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['id', 'image']

class ActivitySerializer(serializers.ModelSerializer):
    images = ActivityImageSerializer(many=True, read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'name', 'description', 'images','time','location']


class DayPlanSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True, read_only=True)
    stay = StaySerializer(read_only=True)
    meals = MealSerializer(many=True, read_only=True)
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta:
        model = DayPlan
        fields = ['id', 'day_number','night', 'description', 'places', 'stay', 'meals', 'activities']




class BusSerializer2(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)

    class Meta:
        model = Bus
        fields = [
            'id',
            'vendor',
            'bus_name',
            'bus_number',
            'capacity',
            'vehicle_description',
            'travels_logo',
            'rc_certificate',
            'license',
            'contract_carriage_permit',
            'passenger_insurance',
            'vehicle_insurance',
            'base_price',
            'price_per_km',
            'amenities'
        ]



class PackageReadSerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, read_only=True)
    buses = BusSerializer2(many=True, read_only=True)
    nights = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    sub_category_name = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id','sub_category', 'sub_category_name', 'category',
            'header_image', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'buses', 'day_plans',
            'created_at', 'updated_at', 'bus_location',
            'price_per_person', 'extra_charge_per_km'
        ]

    def get_nights(self, obj):
        return obj.day_plans.filter(night=True).count()

    def get_category(self, obj):
        return obj.sub_category.category.name
    
    def get_sub_category_name(self, obj):
        return obj.sub_category.name



class PackageSerializerPUT(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, required=False)
    buses = serializers.PrimaryKeyRelatedField(many=True, queryset=Bus.objects.all(), required=False)

    class Meta:
        model = Package
        fields = '__all__'

    def update(self, instance, validated_data):
        day_plans_data = validated_data.pop('day_plans', None)
        buses_data = validated_data.pop('buses', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if buses_data is not None:
            instance.buses.set(buses_data)

        if day_plans_data is not None:
            instance.day_plans.all().delete()  
            for plan_data in day_plans_data:
                DayPlan.objects.create(package=instance, **plan_data)

        return instance
# -----------------------------------------






class VendorBankDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = VendorBankDetail
        fields = '__all__'
        read_only_fields = ['vendor']

    def validate_account_number(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Account number must contain only digits.")
        if len(value) < 9 or len(value) > 18:
            raise serializers.ValidationError("Account number should be between 9 to 18 digits.")
        return value

    def validate_ifsc_code(self, value):
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value):
            raise serializers.ValidationError("Enter a valid IFSC code (e.g., SBIN0001234).")
            raise serializers.ValidationError("Enter a valid IFSC code (e.g., SBIN0001234).")            
        return value

    def validate_payout_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payout amount must be greater than zero.")
        return value

    def validate_payout_mode(self, value):
        allowed_modes = ['BANK_TRANSFER', 'UPI', 'WALLET']
        if value.upper() not in allowed_modes:
            raise serializers.ValidationError(f"Payout mode must be one of {allowed_modes}.")
        return value.upper()

    def validate_phone_number(self, value):
        if value and not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError("Enter a valid 10-digit Indian phone number.")
        return value

    def validate_email_id(self, value):
        if value and not re.match(r'^\S+@\S+\.\S+$', value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value
    




class BusFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusFeature
        fields = ['id', 'name']






class VendorNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorNotification
        fields = ['id', 'description', 'is_read', 'created_at']




# VENDOR SIDE HOME PAGE-----------------

class BusBookingRevenueSerializer(serializers.Serializer):
    bus_id = serializers.IntegerField()
    bus_name = serializers.CharField()
    total_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_advance_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_balance_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_travelers = serializers.IntegerField()
    from_location = serializers.CharField()
    to_location = serializers.CharField()
    total_monthly_revenue = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)





class PackageBookingRevenueSerializer(serializers.Serializer):
    package_places = serializers.CharField()
    total_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_advance_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_balance_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_travelers = serializers.IntegerField()




class BusBookingLatestSerializer(serializers.ModelSerializer):
    total_travelers = serializers.SerializerMethodField()   
    from_to_location = serializers.SerializerMethodField()  

    class Meta:
        model = BusBooking
        fields = ['id','from_to_location', 'total_amount', 'total_travelers', 'start_date']



    def get_from_to_location(self, obj):
        return f"{obj.from_location} to {obj.to_location}"

    def get_total_travelers(self, obj):
        return obj.travelers.count() 




class TravelerSerializer(serializers.ModelSerializer):
    """Serializer for individual traveler details"""
    class Meta:
        model = Travelers
        fields = ['first_name', 'last_name', 'gender', 'dob', 'email', 'mobile', 'place','age' ,'city','id_proof']

class BusBookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for the full bus booking details"""
    user = serializers.StringRelatedField()  
    bus = serializers.StringRelatedField()   
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    travelers = TravelerSerializer(many=True) 
    bus_number = serializers.CharField(source='bus.bus_number', read_only=True)
    trip_status = serializers.CharField(read_only=True) 
    base_price = serializers.DecimalField(source='bus.base_price', max_digits=10, decimal_places=2, read_only=True)
    payment_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_type = serializers.SerializerMethodField()


    class Meta:
        model = BusBooking
        fields = [
            'id', 'start_date', 'from_location', 'to_location',
            'total_amount', 'advance_amount', 'balance_amount', 'payment_status', 
            'user', 'bus','bus_number', 'trip_status', 'travelers','base_price','payment_date','payment_type'
        ]


    def get_payment_type(self, obj):
        if obj.payment_status == 'partial':
            return 'advanced_only'
        elif obj.payment_status == 'paid':
            return 'full'
        return 'unknown'


class PackageBookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for the full package booking details"""
    user = serializers.StringRelatedField()   
    package = serializers.StringRelatedField()   
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    travelers = TravelerSerializer(many=True)   
    # trip_status = serializers.CharField(source='trip_status')
    trip_status = serializers.CharField()
    bus_number = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    payment_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_type = serializers.SerializerMethodField()
    paid_advance_only = serializers.SerializerMethodField()


    class Meta:
        model = PackageBooking
        fields = [
            'id', 'start_date', 'total_travelers', 'total_amount', 'advance_amount', 
            'balance_amount', 'payment_status', 'user', 'package', 'travelers','trip_status','bus_number','from_location','to_location',
            'base_price', 'payment_date', 'payment_type', 'paid_advance_only'
        ]


    
    def get_bus_number(self, obj):
        buses = obj.package.buses.all()
        return buses[0].bus_number if buses.exists() else None

    def get_base_price(self, obj):
        buses = obj.package.buses.all()
        return str(buses[0].base_price) if buses.exists() and buses[0].base_price is not None else None

    def get_payment_type(self, obj):
        if obj.payment_status == 'partial':
            return 'advance_only'
        elif obj.payment_status == 'paid':
            return 'full'
        return 'unknown'

    def get_paid_advance_only(self, obj):
        return obj.payment_status == 'partial'





class BusBookingBasicSerializer(serializers.ModelSerializer):
    bus_number = serializers.CharField(source='bus.bus_number')
    commission_amount = serializers.SerializerMethodField()
    trip_type = serializers.SerializerMethodField()
    total_members = serializers.SerializerMethodField()
    one_member_name = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()
    earnings = serializers.SerializerMethodField() 

    class Meta:
        model = BusBooking
        fields = ['booking_id','bus_number', 'from_location', 'to_location', 'trip_status','total_amount','commission_amount','trip_type','total_members',
            'one_member_name','created_date','earnings','balance_amount']



    def get_commission_amount(self, obj):
        try:
            commission = AdminCommission.objects.get(
                booking_type='bus',
                booking_id=obj.id
            )
            return {
                "advance_amount": commission.advance_amount,
                "commission_percentage": commission.commission_percentage,
                "revenue_to_admin": commission.revenue_to_admin,
                "referral_deduction": commission.referral_deduction
            }
        except AdminCommission.DoesNotExist:
            return None
    

    def get_trip_type(self, obj):
        return "Two Way"
        
    def get_total_members(self, obj):
        return obj.travelers.count()

    def get_one_member_name(self, obj):
        first_traveler = obj.travelers.first()
        if first_traveler:
            if first_traveler.last_name:
                return f"{first_traveler.first_name} {first_traveler.last_name}"
            return first_traveler.first_name
        return None
    
    def get_created_date(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')
    
    def get_earnings(self, obj):
        commission_amount = self.get_commission_amount(obj) or 0
        return obj.total_amount - commission_amount







class BusInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = ['bus_number', 'bus_name', 'capacity']


class BusBookingDetailSerializer222(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField()
    bus = BusInfoSerializer()
    trip_status = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    payment_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_type = serializers.SerializerMethodField()
    paid_advance_only = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = [
            'id', 'user', 'bus', 'from_location', 'to_location',
            'start_date', 'total_amount', 'advance_amount',
            'balance_amount', 'payment_status',
            'travelers','trip_status','booking_status','cancellation_reason','created_at',
            'payment_date', 'base_price',
            'payment_type', 'paid_advance_only'
        ]

    def get_trip_status(self, obj):
        if obj.payment_status in ['pending', 'partial', 'paid']:
            return "scheduled"
        elif obj.payment_status == 'cancelled':
            return "cancelled"
        else:
            return "unknown"   
        
    def get_base_price(self, obj):
        return obj.bus.base_price if obj.bus and obj.bus.base_price else None

    def get_payment_type(self, obj):
        if obj.payment_status == 'partial':
            return 'advance_only'
        elif obj.payment_status == 'paid':
            return 'full'
        return 'unknown'

    def get_paid_advance_only(self, obj):
        return obj.payment_status == 'partial'



from decimal import Decimal

class PackageBookingEarnigsSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    commission = serializers.SerializerMethodField()  
    earnings = serializers.SerializerMethodField()   
    trip_type = serializers.SerializerMethodField() 
    total_members = serializers.SerializerMethodField()  
    one_member_name = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()


    class Meta:
        model = PackageBooking
        fields = ['id', 'package_name', 'total_amount', 'payment_status', 'commission', 'earnings','trip_type','total_members','one_member_name','created_at','from_location','to_location']

    def get_commission(self, obj):
        try:
            commission = AdminCommission.objects.get(
                booking_type='package',
                booking_id=obj.id
            )
            return {
                "advance_amount": commission.advance_amount,
                "commission_percentage": commission.commission_percentage,
                "revenue_to_admin": commission.revenue_to_admin,
                "referral_deduction": commission.referral_deduction
            }
        except AdminCommission.DoesNotExist:
            return None

    def get_earnings(self, obj):
        commission = Decimal(self.get_commission(obj))   
        return obj.total_amount - commission
    
    def get_trip_type(self, obj):
        return "Two Way"
    def get_total_members(self, obj):
        return obj.total_travelers  
    def get_created_at(self, obj):
        return obj.created_at.date() if obj.created_at else None

   
    def get_one_member_name(self, obj):
        first_traveler = obj.travelers.first()
        if first_traveler:
            if first_traveler.last_name:
                return f"{first_traveler.first_name} {first_traveler.last_name}"
            return first_traveler.first_name
        return None








class PackageBookingDetailSerializer222(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')
    start_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    travelers = serializers.SerializerMethodField()
    main_traveler_name = serializers.SerializerMethodField() 
    bus_numbers = serializers.SerializerMethodField()
    # trip_status = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    payment_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_type = serializers.SerializerMethodField()
    paid_advance_only = serializers.SerializerMethodField()

 
    class Meta:
        model = PackageBooking
        fields = [
            'id', 'user', 'package_name', 'start_date', 'total_amount', 'advance_amount', 'balance_amount',
            'payment_status',  'created_at', 'cancellation_reason',
            'total_travelers', 'from_location', 'to_location', 'travelers','main_traveler_name','booking_status','bus_numbers','trip_status',
            'base_price', 'payment_type', 'paid_advance_only','payment_date'
        ]


    def get_base_price(self, obj):
        first_bus = obj.package.buses.first()
        return first_bus.base_price if first_bus and first_bus.base_price else None

    def get_payment_type(self, obj):
        if obj.payment_status == 'partial':
            return 'advance_only'
        elif obj.payment_status == 'paid':
            return 'full'
        return 'unknown'

    def get_paid_advance_only(self, obj):
        return obj.payment_status == 'partial'


    def get_travelers(self, obj):
        travelers = Travelers.objects.filter(package_booking=obj)
        return [
            {
                "id": traveler.id,
                "first_name": traveler.first_name,
                "last_name": traveler.last_name,
                "gender": traveler.get_gender_display(),
                "age": traveler.age,
                "dob": traveler.dob,
                "email": traveler.email,
                "mobile": traveler.mobile,
                "place": traveler.place,
                "city": traveler.city,
                "id_proof": traveler.id_proof.url if traveler.id_proof else None,
                "created_at": traveler.created_at,
            }
            for traveler in travelers
        ]
    
    



    def get_main_traveler_name(self, obj):
        traveler = Travelers.objects.filter(package_booking=obj).first()
        if traveler:
            return f"{traveler.first_name} {traveler.last_name}"
        return None
    
    def get_bus_numbers(self, obj):
        return list(obj.package.buses.values_list('bus_number', flat=True))




class CombinedBookingSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()   
    from_location = serializers.CharField()
    to_location = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    created_at = serializers.DateTimeField()
    members_count = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField() 
    cancellation_reason = serializers.CharField()

    def get_type(self, obj):
        return "bus" if isinstance(obj, BusBooking) else "package"

    def get_name(self, obj):
        traveler = obj.travelers.order_by('created_at').first()
        if traveler:
            return f"{traveler.first_name} {traveler.last_name or ''}".strip()
        return "No Name"

    def get_members_count(self, obj):
        return obj.travelers.count()

    def get_phone_number(self, obj):
        traveler = obj.travelers.order_by('created_at').first()
        return traveler.mobile if traveler and traveler.mobile else ""







class VendorBusyDateSerializer(serializers.ModelSerializer):
    bus_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Bus.objects.all(),
        write_only=True,
        required=False
    )
    buses = BusSerializer(many=True, read_only=True)

    class Meta:
        model = VendorBusyDate
        fields = ['id', 'date', 'from_time', 'to_time', 'reason', 'bus_ids', 'buses']

    def validate(self, data):
        from_time = data.get('from_time')
        to_time = data.get('to_time')

        if from_time and to_time and from_time >= to_time:
            raise serializers.ValidationError("From time must be earlier than to time.")
        return data

    def update(self, instance, validated_data):
        # Safely extract bus_ids using .get() instead of .pop()
        bus_ids = validated_data.get('bus_ids', None)

        # Remove bus_ids so it's not treated as a regular model field
        if 'bus_ids' in validated_data:
            del validated_data['bus_ids']

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Only set buses if bus_ids is a list (not None)
        if bus_ids is not None:
            instance.buses.set(bus_ids)

        return instance





class PackageBookingBasicSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')  
    start_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    booking_status = serializers.BooleanField()
    created_at = serializers.DateTimeField()

    class Meta:
        model = PackageBooking
        fields = ['id', 'package_name', 'start_date', 'total_amount', 'payment_status', 'booking_status', 'created_at']





class BusDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusDriverDetail
        fields = ['name', 'place', 'phone_number', 'driver_image', 'license_image', 'experience', 'age','email']





class AcceptedBusBookingSerializer(serializers.ModelSerializer):
    driver_detail = BusDriverDetailSerializer(read_only=True)
    traveler = serializers.SerializerMethodField()
    all_travelers = serializers.SerializerMethodField()
    balance_amount = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = [
            'id', 'start_date', 'total_amount', 'advance_amount', 'trip_status', 'balance_amount',
            'payment_status', 'booking_status', 'from_location', 'to_location', 'created_at',
            'total_travelers', 'male', 'female', 'children', 'cancellation_reason',
            'driver_detail', 'traveler', 'all_travelers'
        ]

    def get_traveler(self, obj):
        traveler = obj.travelers.first()
        return TravelerSerializer(traveler).data if traveler else None

    def get_all_travelers(self, obj):
        return TravelerSerializer(obj.travelers.all(), many=True).data

    def get_balance_amount(self, obj):
        return obj.total_amount - obj.advance_amount if obj.total_amount and obj.advance_amount else 0




class PackageDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageDriverDetail
        fields = ['name', 'place', 'phone_number', 'driver_image', 'license_image', 'experience', 'age','email']


class AcceptedPackageBookingSerializer(serializers.ModelSerializer):
    driver_detail = PackageDriverDetailSerializer(read_only=True)
    traveler = serializers.SerializerMethodField()
    all_travelers = serializers.SerializerMethodField()
    balance_amount = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = [
            'id', 'start_date', 'total_amount', 'advance_amount', 'trip_status', 'balance_amount',
            'payment_status', 'booking_status', 'from_location', 'to_location', 'created_at',
            'total_travelers', 'male', 'female', 'children', 'cancellation_reason',
            'driver_detail', 'traveler', 'all_travelers'
        ]

    def get_traveler(self, obj):
        traveler = obj.travelers.first()
        return TravelerSerializer(traveler).data if traveler else None

    def get_all_travelers(self, obj):
        return TravelerSerializer(obj.travelers.all(), many=True).data

    def get_balance_amount(self, obj):
        return obj.total_amount - obj.advance_amount if obj.total_amount and obj.advance_amount else 0




class PackageBookingListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageBooking
        fields = ['booking_id', 'start_date', 'total_amount', 'advance_amount', 'payment_status', 'booking_status', 
                  'from_location', 'to_location', 'created_at', 'total_travelers', 'male', 'female', 'children','balance_amount',
                  'cancellation_reason']





class BusBookingRequestSerializer(serializers.ModelSerializer):
    bus_number = serializers.CharField(source='bus.bus_number')
    commission_amount = serializers.SerializerMethodField()
    trip_type = serializers.SerializerMethodField()
    total_travelers = serializers.SerializerMethodField()
    first_traveler_name = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = [
            'booking_id', 'bus_number', 'from_location', 'to_location', 'total_amount',
            'commission_amount', 'trip_type', 'total_travelers', 'first_traveler_name',
            'created_date','paid_amount'
        ]

    def get_commission_amount(self, obj):
        commission = AdminCommission.objects.filter(booking_type='bus', booking_id=obj.id).first()
        return commission.revenue_to_admin if commission else 0

    def get_trip_type(self, obj):
        return "Two Way"

    def get_total_travelers(self, obj):
        return obj.travelers.count()

    def get_first_traveler_name(self, obj):
        first_traveler = obj.travelers.first()
        if first_traveler:
            return f"{first_traveler.first_name} {first_traveler.last_name or ''}".strip()
        return None

    def get_created_date(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')






class PackageBookingREQUESTSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')   
    commission_amount = serializers.SerializerMethodField()
    trip_type = serializers.SerializerMethodField()
    total_members = serializers.SerializerMethodField()
    one_member_name = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = [
            'booking_id','package_name', 'from_location', 'to_location', 'total_amount',
            'commission_amount', 'trip_type', 'total_members', 'one_member_name',
            'created_date', 'paid_amount'
        ]

    def get_commission_amount(self, obj):
        commission = AdminCommission.objects.filter(booking_type='package', booking_id=obj.id).first()
        if commission:
            return commission.revenue_to_admin
        return None

    def get_trip_type(self, obj):
        return "Two Way"

    def get_total_members(self, obj):
        return obj.total_travelers

    def get_one_member_name(self, obj):
        first_traveler = obj.travelers.first()
        if first_traveler:
            if first_traveler.last_name:
                return f"{first_traveler.first_name} {first_traveler.last_name}"
            return first_traveler.first_name
        return None

    def get_created_date(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')

    def get_earnings(self, obj):
        commission_amount = self.get_commission_amount(obj) or 0
        return obj.total_amount - commission_amount 
    







class BaseBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusBooking  # or PackageBooking
        fields = '__all__'














    