from rest_framework import serializers
from admin_panel.models import Vendor
from .models import User
from vendors.serializers import *
from .models import AdminCommissionSlab, AdminCommission
from bookings.models import *
from .models import *
from reviews.models import BusReview
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
            'bus_name', 'bus_number', 'capacity', 'vehicle_description',
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




class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'mobile', 'email', 'role', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user







# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'name', 'email', 'mobile', ]



class UserSerializer(serializers.ModelSerializer):
    place = serializers.CharField(source='city')  # Using 'city' as 'place'

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'mobile', 'place', 'is_active']










# --------------------------------- Advertisement-----------------

class AdvertisementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        fields = ['title', 'description', 'image']


class LimitedDealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimitedDealImage
        fields = ['image']


class LimitedDealSerializer(serializers.ModelSerializer):
    # images = serializers.ListField(
    #     child=serializers.ImageField(),
    #     write_only=True,
    #     required=False 
    # )
    images = LimitedDealImageSerializer(many=True, read_only=True)

    class Meta:
        model = LimitedDeal
        fields = ['title', 'description', 'images']

    def create(self, validated_data):
        images = validated_data.pop('images', [])   
        limited_deal = LimitedDeal.objects.create(**validated_data)

        for img in images:
            LimitedDealImage.objects.create(deal=limited_deal, image=img)

        return limited_deal


class FooterSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSection
        fields = ['title', 'description', 'image']


# --------------------------------------------------------



class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ['image', 'description',]


class SightSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sight
        fields = ['title', 'description', 'season_description','image']



class SightListSerializer(serializers.ModelSerializer):
    experiences = ExperienceSerializer(many=True, read_only=True)

    class Meta:
        model = Sight
        fields = ['id', 'title', 'description', 'season_description', 'experiences','image']







class AdminBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source='user.full_name')
    date = serializers.DateField(source='start_date')
    category = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    cost = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)

    def get_category(self, obj):
        return "Bus" if isinstance(obj, BusBooking) else "Package"

    def get_trip(self, obj):
        if isinstance(obj, BusBooking):
            return f"{obj.from_location} to {obj.to_location}"
        elif isinstance(obj, PackageBooking):
            return f"{obj.package.places}"   
        return ""






class AdminCommissionSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminCommissionSlab
        fields = '__all__'

class AdminCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminCommission
        fields = '__all__'


class AdminBaseBookingSerializer(serializers.ModelSerializer):
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        abstract = True
        fields = ['id', 'user', 'start_date', 'total_amount', 'advance_amount', 
                 'payment_status', 'booking_status', 'trip_status', 'created_at', 
                 'balance_amount', 'cancelation_reason', 'total_travelers', 
                 'male', 'female', 'children', 'from_location', 'to_location']
        read_only_fields = ['id', 'created_at', 'balance_amount']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

class AdminBusBookingSerializer(AdminBaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BusBooking
        fields = AdminBaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way', 'travelers', 'driver_detail'
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }
    
    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data

class AdminPackageBookingSerializer(AdminBaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PackageBooking
        fields = AdminBaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers', 'driver_detail'
        ]
        read_only_fields = AdminBaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }
    
    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data


class AdminBusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    bus_name = serializers.CharField(source="bus.bus_name", read_only=True)  # Include bus name

    class Meta:
        model = BusReview
        fields = ["user_name", "bus_name", "rating", "comment", "created_at"]




class RecentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'created_at']




class TopVendorSerializer(serializers.Serializer):
    name = serializers.CharField()
    place = serializers.CharField()
    total_booking_count = serializers.IntegerField()








class UserBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaseBooking  
        fields = ['id', 'start_date', 'total_amount', 'booking_status', 'trip_status']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if isinstance(instance, BusBooking):
            representation['item_type'] = 'Bus'
        elif isinstance(instance, PackageBooking):
            representation['item_type'] = 'Package'
        
        return representation




class BusBookingSerializer08(serializers.ModelSerializer):
    class Meta:
        model = BusBooking
        fields = ['id', 'start_date', 'total_amount', 'booking_status', 'trip_status']

class PackageBookingSerializer08(serializers.ModelSerializer):
    class Meta:
        model = PackageBooking
        fields = ['id', 'start_date', 'total_amount', 'booking_status', 'trip_status']









class BookingDisplaySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    start_date = serializers.DateField()
    booking_status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    from_location = serializers.CharField()
    to_location = serializers.CharField()
    booking_type = serializers.SerializerMethodField()
    user = serializers.StringRelatedField()
    total_members = serializers.SerializerMethodField()
    default_member_name = serializers.SerializerMethodField()

    def get_booking_type(self, obj):
        return 'Bus' if hasattr(obj, 'bus') else 'Package'
    


    def get_total_members(self, obj):
        return obj.male + obj.female + obj.children

    def get_default_member_name(self, obj):
        traveler = obj.travelers.first()
        if traveler:
            return f"{traveler.first_name} {traveler.last_name or ''}".strip()
        return f"Traveler {obj.id}"








class BusTravelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusTravelImage
        fields = ['image']


class BusFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusFeature
        fields = ['id', 'name']  


class BusAdminSerializer(serializers.ModelSerializer):
    travels_name = serializers.CharField(source='vendor.full_name')   
    images = BusTravelImageSerializer(source='travel_images', many=True, read_only=True)
    bus_type = serializers.SerializerMethodField()

    class Meta:
        model = Bus
        fields = [
            'id',
            'travels_name',
            'bus_number',
            'capacity',
            'vehicle_rc_number',
            'status',
            'bus_type',
            'images',
        ]


    def get_bus_type(self, obj):
        return {feature.id: feature.name for feature in obj.features.all()}



class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name']  # customize as needed



class BusDetailSerializerADMIN(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name')
    bus_type = BusFeatureSerializer(source='features', many=True)
    amenities = AmenitySerializer(many=True)
    travels_logo = serializers.ImageField()
    travel_images = BusTravelImageSerializer(many=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)


    class Meta:
        model = Bus
        fields = [
            'id',
            'vendor_name',
            'bus_name',
            'bus_number',
            'capacity',
            'vehicle_description',
            'vehicle_rc_number',
            'travels_logo',
            'travel_images',
            'rc_certificate',
            'license',
            'contract_carriage_permit',
            'passenger_insurance',
            'vehicle_insurance',
            'base_price',
            'price_per_km',
            'minimum_fare',
            'status',
            'bus_type',
            'amenities',
            'average_rating',
            'total_reviews',
        ]


class BusShortSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name')
    features = BusFeatureSerializer(many=True)

    class Meta:
        model = Bus
        fields = ['vendor_name', 'bus_number', 'features']



class PackageListSerializer(serializers.ModelSerializer):
    buses = BusShortSerializer(many=True)
    duration = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id',
            'places',
            'duration',
            'price_per_person',
            'image',
            'buses'
        ]

    def get_duration(self, obj):
        return f"{obj.days} Days / {obj.nights} Nights"
    
    def get_image(self, obj):
        first_image = obj.package_images.first()
        if first_image and first_image.image:
            return first_image.image.url   
        return None
    


class PackageDetailSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name')
    buses = serializers.SerializerMethodField()
    header_image = serializers.SerializerMethodField()
    day_plans = DayPlanSerializer(many=True)

    class Meta:
        model = Package
        fields = [
            'id', 'vendor_name', 'buses', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'price_per_person',
            'header_image', 'day_plans'
        ]

    def get_buses(self, obj):
        return [bus.bus_number for bus in obj.buses.all()]

    def get_header_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.header_image.url) if obj.header_image else None




