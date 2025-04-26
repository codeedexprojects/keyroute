from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from admin_panel.models import Vendor, User
from .models import *
from django.db import transaction
from django.core.exceptions import ValidationError
import re
from bookings.models import *
import json


class VendorSerializer(serializers.ModelSerializer):

    # mobile = serializers.CharField(source='user.mobile', read_only=True)
    mobile = serializers.CharField(write_only=True) 
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Vendor
        fields = [
            'mobile', 'email_address', 'password', 'full_name',  
            'travels_name', 'location', 'landmark', 'address', 
            'city', 'state', 'pincode','district'
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
        # email = validated_data.pop('email', None) 
        email = validated_data.get('email_address') or None  
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




class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name','icon']





class BusSerializer(serializers.ModelSerializer):


    features = serializers.PrimaryKeyRelatedField(
        queryset=BusFeature.objects.all(), many=True, required=False
    )
    amenities = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(),
        many=True,
        required=False
    )

    # amenities = AmenitySerializer(many=True, read_only=True)
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['amenities'] = AmenitySerializer(instance.amenities.all(), many=True).data
        return rep

    
    class Meta:
        model = Bus
        fields = [
            'id',
            'features',
            'id',
            'features',
            'minimum_fare',
            'bus_travel_images',

            'bus_name', 'bus_number',  'capacity', 'vehicle_description',
            'vehicle_rc_number', 'travels_logo', 'rc_certificate', 'license',
            'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance', 'bus_view_images','amenities','base_price', 'price_per_km' 
        ]

    

    bus_view_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True
    )

    bus_travel_images = serializers.ListField(
    child=serializers.ImageField(),
    write_only=True,
    required=False
    )


  
    def get_amenities(self, obj):
        return [amenity.name for amenity in obj.amenities.all()]
  
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
        
        features = validated_data.pop('features', [])
        vendor = self.context['vendor']
        travel_images = validated_data.pop('bus_travel_images', [])

        bus = Bus.objects.create(vendor=vendor, **validated_data)

        for image in bus_images:
            BusImage.objects.create(bus=bus, bus_view_image=image)

        for travel_img in travel_images:
            BusTravelImage.objects.create(bus=bus, image=travel_img)

        bus.amenities.set(amenities)
        bus.features.set(features) 
        return bus














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


def validate_days_nights(days, nights):
    if days < 0 or nights < 0:
        raise ValidationError("Days and nights must be non-negative numbers.")

def validate_places(places):
    if not places.strip():
        raise ValidationError("Places field cannot be empty.")


class PackageImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageImage
        fields = ['image']







class PackageSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)  
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)  
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    package_images = PackageImageSerializer(many=True, write_only=True)

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
        fields = ['day_number', 'places', 'stay', 'meals', 'activities','description']

class PackageSerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, write_only=True)
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)

    day_plans_read = DayPlanSerializer(source='dayplan_set', many=True, read_only=True)
    

    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category', 'header_image', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'buses', 
            'day_plans','day_plans_read'
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
        print('helllo')
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
            'sub_category', 'header_image', 'places', 'days', 'nights',
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
        fields = ['id', 'hotel_name', 'description', 'images']


class MealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealImage
        fields = ['id', 'image']

class MealSerializer(serializers.ModelSerializer):
    images = MealImageSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = ['id', 'type', 'description', 'images']


class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['id', 'image']

class ActivitySerializer(serializers.ModelSerializer):
    images = ActivityImageSerializer(many=True, read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'name', 'description', 'images']


class DayPlanSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True, read_only=True)
    stay = StaySerializer(read_only=True)
    meals = MealSerializer(many=True, read_only=True)
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta:
        model = DayPlan
        fields = ['id', 'day_number', 'description', 'places', 'stay', 'meals', 'activities']


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
            'vehicle_rc_number',
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

    class Meta:
        model = Package
        fields = [
            'id', 'sub_category', 'header_image', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'buses', 'day_plans',
            'created_at', 'updated_at','bus_location', 'price_per_person', 'extra_charge_per_km'
        ]



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
        fields = ['first_name', 'last_name', 'gender', 'dob', 'email', 'mobile', 'place', 'city']

class BusBookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for the full bus booking details"""
    user = serializers.StringRelatedField()  
    bus = serializers.StringRelatedField()   
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    travelers = TravelerSerializer(many=True)  

    class Meta:
        model = BusBooking
        fields = [
            'id', 'start_date', 'from_location', 'to_location', 'one_way',
            'total_amount', 'advance_amount', 'balance_amount', 'payment_status', 
            'user', 'bus', 'travelers'
        ]


class PackageBookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for the full package booking details"""
    user = serializers.StringRelatedField()   
    package = serializers.StringRelatedField()   
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    travelers = TravelerSerializer(many=True)   

    class Meta:
        model = PackageBooking
        fields = [
            'id', 'start_date', 'total_travelers', 'total_amount', 'advance_amount', 
            'balance_amount', 'payment_status', 'user', 'package', 'travelers'
        ]







class BusBookingBasicSerializer(serializers.ModelSerializer):
    bus_number = serializers.CharField(source='bus.bus_number')

    class Meta:
        model = BusBooking
        fields = ['id','bus_number', 'from_location', 'to_location', 'total_amount', 'payment_status']








class BusInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = ['bus_number', 'bus_name', 'capacity']


class BusBookingDetailSerializer(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField()
    bus = BusInfoSerializer()

    class Meta:
        model = BusBooking
        fields = [
            'id', 'user', 'bus', 'from_location', 'to_location',
            'start_date', 'total_amount', 'advance_amount',
            'balance_amount', 'payment_status', 'one_way',
            'travelers'
        ]





class PackageBookingBasicSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')
    start_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()

    class Meta:
        model = PackageBooking
        fields = ['id','package_name', 'start_date', 'total_amount', 'payment_status']




class PackageBookingDetailSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.places')
    start_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    travelers = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = ['package_name', 'start_date', 'total_amount', 'payment_status', 'travelers']

    def get_travelers(self, obj):
        travelers = Travelers.objects.filter(package_booking=obj)
        return [{"name": f"{traveler.first_name} {traveler.last_name}",
                 "gender": traveler.get_gender_display(),
                 "email": traveler.email,
                 "mobile": traveler.mobile} for traveler in travelers]


class CombinedBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()   
    from_location = serializers.CharField()
    to_location = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_status = serializers.CharField()
    created_at = serializers.DateTimeField()
    members_count = serializers.SerializerMethodField()

    def get_type(self, obj):
        return "bus" if isinstance(obj, BusBooking) else "package"

    def get_name(self, obj):
        traveler = obj.travelers.first()
        if traveler:
            return f"{traveler.first_name} {traveler.last_name or ''}".strip()
        return "No Name"

    def get_members_count(self, obj):
        return obj.travelers.count()






class VendorBusyDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBusyDate
        fields = ['id','date', 'from_time', 'to_time', 'reason']

    def validate(self, data):
        from_time = data.get('from_time')
        to_time = data.get('to_time')

        if from_time and to_time and from_time >= to_time:
            raise serializers.ValidationError("From time must be earlier than to time.")
        return data
