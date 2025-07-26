from rest_framework import serializers
from admin_panel.models import Vendor
from .models import User
from vendors.serializers import *
from .models import AdminCommissionSlab, AdminCommission
from bookings.models import *
from .models import *
from django.db.models import Q, Count
from reviews.models import BusReview,PackageReview,AppReview
class VendorSerializer1(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'


class AdminVendorSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = Vendor
        fields = [
            'user_id',
            'mobile',
            'password',
            'email_address',
            'full_name',
            'travels_name',
            'location',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'district'
        ]

    def validate_mobile(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError('Mobile number must be at least 10 digits long.')
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError('Mobile number already registered.')
        return value

    def validate_email_address(self, value):
        if value:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError('Email already registered with a user.')
            if Vendor.objects.filter(email_address=value).exists():
                raise serializers.ValidationError('Email already registered with another vendor.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Password must be at least 6 characters long.')
        return value

    def create(self, validated_data):
        mobile = validated_data.pop('mobile')
        password = validated_data.pop('password')
        email = validated_data.get('email_address')

        # Create user
        user = User.objects.create_user(
            mobile=mobile,
            email=email,
            password=password,
            role=User.VENDOR,
        )

        # Set optional fields if you want
        user.state = validated_data.get('state')
        user.district = validated_data.get('district')
        user.city = validated_data.get('city')
        user.save()

        validated_data['user'] = user
        return Vendor.objects.create(**validated_data)

class VendorBusyDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBusyDate
        fields = ['date', 'from_time', 'to_time', 'reason']




class VendorFullSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')
    phone = serializers.CharField(source='user.mobile')
    state = serializers.CharField(source='user.state')    
    district = serializers.CharField(source='user.district')

    buses = BusSerializer(source='bus_set', many=True, read_only=True)
    packages = PackageSerializer(source='package_set', many=True, read_only=True)
    busy_dates = VendorBusyDateSerializer(many=True, read_only=True)

    bus_count = serializers.SerializerMethodField()
    package_count = serializers.SerializerMethodField()
    ongoing_buses = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'user_id',
            'email_address',
            'full_name',
            'phone',
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
            'packages',
            'busy_dates',
        ]

    def get_bus_count(self, obj):
        return obj.bus_set.count()

    def get_package_count(self, obj):
        return obj.package_set.count()

    def get_ongoing_buses(self, obj):
        ongoing_buses = obj.bus_set.all()[:2]
        return BusSerializer(ongoing_buses, many=True).data

    def get_available_packages(self, obj):
        available_packages = obj.package_set.filter(status='available')
        data = []
        for package in available_packages:
            data.append({
                'package_name': f"{package.sub_category.name} - {package.places}",
                'travels_name': obj.travels_name,
                'bus_numbers': [bus.bus_number for bus in package.buses.all()],
                'location': package.bus_location,
                'days': package.days,
                'day_plans': [
                    {
                        'day_number': day.day_number,
                        'description': day.description,
                        'night': day.night
                    }
                    for day in package.day_plans.all()
                ]
            })
        return data




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
            'travels_logo', 'rc_certificate', 'license',
            'contract_carriage_permit', 'passenger_insurance', 'vehicle_insurance',
            'bus_view_images', 'amenities', 'base_price', 'price_per_km'
        ]



# ADMIN SIDE VENDOR PACKAGE LISING
class AdminPackageListSerializer(serializers.ModelSerializer):
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id',
            'places',
            'days',
            'ac_available',
            'guide_included', 
            'sub_category_name',
            'image'
        ]

    def get_image(self, obj):
        first_image = obj.package_images.first()
        if first_image and first_image.image:
            request = self.context.get('request')
            return request.build_absolute_uri(first_image.image.url) if request else first_image.image.url
        return None




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


class PackageCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageCategory
        fields = ['id', 'name', 'image']



class PackageSubCategorySerializer(serializers.ModelSerializer):
    category = PackageCategorySerializer(read_only=True)

    class Meta:
        model = PackageSubCategory
        fields = ['id', 'name', 'image', 'category']


class BusSerializer(serializers.ModelSerializer):
    amenities = serializers.StringRelatedField(many=True)
    features = serializers.StringRelatedField(many=True)

    class Meta:
        model = Bus
        fields = [
            'id', 'bus_name', 'bus_number', 'capacity', 'vehicle_description',
            'travels_logo', 'rc_certificate', 'license', 'contract_carriage_permit',
            'passenger_insurance', 'vehicle_insurance', 'base_price', 'base_price_km',
            'price_per_km', 'night_allowance', 'minimum_fare', 'status', 'location',
            'latitude', 'longitude', 'bus_type', 'is_popular', 'average_rating',
            'total_reviews', 'amenities', 'features'
        ]



class AdminPackageDetailSerializer(serializers.ModelSerializer):
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)
    sub_category_id = serializers.CharField(source='sub_category.id', read_only=True)
    category_name = serializers.SerializerMethodField()
    category_id = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    travels_name = serializers.SerializerMethodField()
    bus_count = serializers.SerializerMethodField()
    package_images = PackageImageSerializer(many=True, read_only=True)
    day_plans = DayPlanSerializer(many=True, read_only=True)
    buses = BusSerializer(many=True, read_only=True)

    price_per_person = serializers.SerializerMethodField()
    extra_charge_per_km = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category_name',
            'vendor_name',
            'sub_category_id',
            'category_name',
            'category_id',
            'package_images',
            'header_image',
            'places',
            'days',
            'ac_available',
            'guide_included',
            'price_per_person',
            'extra_charge_per_km',
            'day_plans',
            'buses',
            'bus_count',
            'travels_name',
            'average_rating',
            'total_reviews',
            'created_at',
            'updated_at'
        ]

    def get_travels_name(self, obj):
        return list(
            obj.buses.select_related('vendor')
                .values_list('vendor__travels_name', flat=True)
                .distinct()
        )

    def get_bus_count(self, obj):
        return obj.buses.count()
    
    def get_category_name(self, obj):
        return obj.sub_category.category.name if obj.sub_category and obj.sub_category.category else None
    
    def get_category_id(self, obj):
        return obj.sub_category.category.name if obj.sub_category and obj.sub_category.category else None

    def get_price_per_person(self, obj):
        return int(obj.price_per_person)

    def get_extra_charge_per_km(self, obj):
        return int(obj.extra_charge_per_km)

    def get_average_rating(self, obj):
        avg = obj.package_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.package_reviews.count()
    



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
        fields = ['id', 'name', 'email', 'mobile', 'place', 'is_active','district','state','created_at']










# --------------------------------- Advertisement-----------------

class AdvertisementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        fields = ['id','title', 'type','subtitle', 'image']


class LimitedDealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimitedDealImage
        fields = ['id','image']


class LimitedDealSerializer(serializers.ModelSerializer):
   
    images = LimitedDealImageSerializer(many=True, read_only=True)

    class Meta:
        model = LimitedDeal
        fields = ['id','title', 'offer','terms_and_conditions', 'images','subtitle']


    def create(self, validated_data):
        images = validated_data.pop('images', [])   
        limited_deal = LimitedDeal.objects.create(**validated_data)

        for img in images:
            LimitedDealImage.objects.create(deal=limited_deal, image=img)

        return limited_deal

class ReferAndEarnSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferAndEarn
        fields = ['id', 'image', 'price', 'created_at']
        read_only_fields = ['id', 'created_at']


class FooterImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterImage
        fields = ['id', 'image', 'uploaded_at']

class FooterSectionSerializer(serializers.ModelSerializer):
    extra_images = FooterImageSerializer(many=True, read_only=True) 
    vendor_name = serializers.SerializerMethodField()
    # package = PackageSerializer() 
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all())
    class Meta:
        model = FooterSection

        fields = ['id', 'package', 'main_image','extra_images','package','vendor_name']
    
    def get_vendor_name(self,obj):
        return obj.package.vendor.full_name


# --------------------------------------------------------
class SightImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SightImage
        fields = ['id', 'image']


class ExperienceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperienceImage
        fields = ['id', 'image']


class ExperienceSerializer(serializers.ModelSerializer):
    images = ExperienceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Experience
        fields = ['id','images', 'description','header','sub_header']


class SightSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sight
        fields = ['id','title', 'description', 'season_description']

class SeasonTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonTime
        fields = '__all__'

class SeasonTimeSerializer2(serializers.ModelSerializer):
    class Meta:
        model = SeasonTime
        fields = ['id', 'from_date', 'to_date', 'description',
                  'icon1', 'icon1_description',
                  'icon2', 'icon2_description',
                  'icon3', 'icon3_description']

class SightListSerializer(serializers.ModelSerializer):
    experiences = ExperienceSerializer(many=True, read_only=True)
    seasons = SeasonTimeSerializer(many=True, read_only=True)

    images = SightImageSerializer(many=True, read_only=True)

    class Meta:
        model = Sight
        fields = ['id', 'title', 'description', 'experiences','seasons','images']









class AdminBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    
    # User details
    name = serializers.CharField(source='user.name')
    mobile = serializers.CharField(source='user.mobile')
    email = serializers.EmailField(source='user.email', read_only=True)
    city = serializers.CharField(source='user.city', read_only=True)
    district = serializers.CharField(source='user.district', read_only=True)
    state = serializers.CharField(source='user.state', read_only=True)

    # Booking info
    date = serializers.DateField(source='start_date')
    booking_date = serializers.DateField(source='created_at')
    category = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    cost = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    balance_amount = serializers.SerializerMethodField()

    # Vendor info
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    def get_category(self, obj):
        return "Bus" if isinstance(obj, BusBooking) else "Package"

    def get_trip(self, obj):
        if isinstance(obj, BusBooking):
            return f"{obj.from_location} to {obj.to_location}"
        elif isinstance(obj, PackageBooking):
            return f"{obj.package.places}"
        return ""

    def get_balance_amount(self, obj):
        return obj.balance_amount

    def get_vendor_name(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.full_name if vendor else None

    def get_vendor_phone(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.phone_no if vendor else None

    def get_vendor_email(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.email_address if vendor else None

    def get_vendor_city(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.city if vendor else None

    def _get_vendor(self, obj):
        if isinstance(obj, BusBooking) and obj.bus and obj.bus.vendor:
            return obj.bus.vendor
        elif isinstance(obj, PackageBooking) and obj.package and obj.package.vendor:
            return obj.package.vendor
        return None







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
                 'balance_amount', 'cancellation_reason', 'total_travelers', 
                 'male', 'female', 'children', 'from_location', 'to_location']
        read_only_fields = ['id', 'created_at', 'balance_amount']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

class AdminBusBookingSerializer(AdminBaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)

    # User contact details
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_city = serializers.CharField(source='user.city', read_only=True)
    user_district = serializers.CharField(source='user.district', read_only=True)
    user_state = serializers.CharField(source='user.state', read_only=True)

    # Vendor contact details
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = AdminBaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'travelers', 'driver_detail',

            # User contact
            'user_name', 'user_mobile', 'user_email', 'user_city', 'user_district', 'user_state',

            # Vendor contact
            'vendor_name', 'vendor_phone', 'vendor_email', 'vendor_city',
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data

    # Vendor methods
    def get_vendor_name(self, obj):
        return obj.bus.vendor.full_name if obj.bus and obj.bus.vendor else None

    def get_vendor_phone(self, obj):
        return obj.bus.vendor.phone_no if obj.bus and obj.bus.vendor else None

    def get_vendor_email(self, obj):
        return obj.bus.vendor.email_address if obj.bus and obj.bus.vendor else None

    def get_vendor_city(self, obj):
        return obj.bus.vendor.city if obj.bus and obj.bus.vendor else None


class AdminPackageBookingSerializer(AdminBaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    bus_count = serializers.SerializerMethodField(read_only=True)

    # User contact details
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_city = serializers.CharField(source='user.city', read_only=True)
    user_district = serializers.CharField(source='user.district', read_only=True)
    user_state = serializers.CharField(source='user.state', read_only=True)

    # Vendor contact details
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = AdminBaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers', 'driver_detail',

            # User contact
            'user_name', 'user_mobile', 'user_email', 'user_city', 'user_district', 'user_state',

            # Vendor contact
            'vendor_name', 'vendor_phone', 'vendor_email', 'vendor_city','bus_count'
        ]
        read_only_fields = AdminBaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data
    
    def get_bus_count(self, obj):
        if obj.package and hasattr(obj.package, 'buses'):
            return obj.package.buses.count()
        return 0

    # Vendor methods
    def get_vendor_name(self, obj):
        return obj.package.vendor.full_name if obj.package and obj.package.vendor else None

    def get_vendor_phone(self, obj):
        return obj.package.vendor.phone_no if obj.package and obj.package.vendor else None

    def get_vendor_email(self, obj):
        return obj.package.vendor.email_address if obj.package and obj.package.vendor else None

    def get_vendor_city(self, obj):
        return obj.package.vendor.city if obj.package and obj.package.vendor else None


class AdminBusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    bus_name = serializers.CharField(source="bus.bus_name", read_only=True)  # Include bus name

    class Meta:
        model = BusReview
        fields = ["user_name", "bus_name", "rating", "comment", "created_at"]




class RecentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'created_at','profile_image']




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
    total_members = serializers.SerializerMethodField()
    default_member_name = serializers.SerializerMethodField()

    # User contact details
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_city = serializers.CharField(source='user.city', read_only=True)
    user_district = serializers.CharField(source='user.district', read_only=True)
    user_state = serializers.CharField(source='user.state', read_only=True)

    # Vendor contact details
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    def get_booking_type(self, obj):
        return 'Bus' if hasattr(obj, 'bus') else 'Package'

    def get_total_members(self, obj):
        return obj.male + obj.female + obj.children

    def get_default_member_name(self, obj):
        traveler = obj.travelers.first()
        if traveler:
            return f"{traveler.first_name} {traveler.last_name or ''}".strip()
        return f"Traveler {obj.id}"

    def get_vendor_name(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.full_name if vendor else None

    def get_vendor_phone(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.phone_no if vendor else None

    def get_vendor_email(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.email_address if vendor else None

    def get_vendor_city(self, obj):
        vendor = self._get_vendor(obj)
        return vendor.city if vendor else None

    def _get_vendor(self, obj):
        if hasattr(obj, 'bus') and obj.bus and obj.bus.vendor:
            return obj.bus.vendor
        elif hasattr(obj, 'package') and obj.package and obj.package.vendor:
            return obj.package.vendor
        return None


from rest_framework import serializers
from bookings.models import BusBooking, PackageBooking, Travelers, BusDriverDetail, PackageDriverDetail

# Travelers Serializer
class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travelers
        fields = '__all__'

# Bus Driver Detail Serializer
class BusDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusDriverDetail
        fields = '__all__'

# Package Driver Detail Serializer
class PackageDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageDriverDetail
        fields = '__all__'

# BusBooking Serializer
class BusBookingSerializer(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, read_only=True)
    driver_detail = BusDriverDetailSerializer(read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    # User contact fields
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_city = serializers.CharField(source='user.city', read_only=True)
    user_district = serializers.CharField(source='user.district', read_only=True)
    user_state = serializers.CharField(source='user.state', read_only=True)

    # Vendor contact fields
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = '__all__'

    def get_vendor_name(self, obj):
        if obj.bus and obj.bus.vendor:
            return obj.bus.vendor.full_name
        return None

    def get_vendor_phone(self, obj):
        if obj.bus and obj.bus.vendor:
            return obj.bus.vendor.phone_no
        return None

    def get_vendor_email(self, obj):
        return obj.bus.vendor.email_address if obj.bus and obj.bus.vendor else None

    def get_vendor_city(self, obj):
        return obj.bus.vendor.city if obj.bus and obj.bus.vendor else None

# PackageBooking Serializer
class PackageBookingSerializer(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, read_only=True)
    driver_detail = PackageDriverDetailSerializer(read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    bus_count = serializers.SerializerMethodField()

    # User contact fields
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_city = serializers.CharField(source='user.city', read_only=True)
    user_district = serializers.CharField(source='user.district', read_only=True)
    user_state = serializers.CharField(source='user.state', read_only=True)

    # Vendor contact fields
    vendor_name = serializers.SerializerMethodField()
    vendor_phone = serializers.SerializerMethodField()
    vendor_email = serializers.SerializerMethodField()
    vendor_city = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = '__all__'

    def get_bus_count(self, obj):
        if obj.package and hasattr(obj.package, 'buses'):
            return obj.package.buses.count()
        return 0

    def get_vendor_name(self, obj):
        return obj.package.vendor.full_name if obj.package and obj.package.vendor else None

    def get_vendor_phone(self, obj):
        return obj.package.vendor.phone_no if obj.package and obj.package.vendor else None

    def get_vendor_email(self, obj):
        return obj.package.vendor.email_address if obj.package and obj.package.vendor else None

    def get_vendor_city(self, obj):
        return obj.package.vendor.city if obj.package and obj.package.vendor else None



class PaymentDetailsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    booking_type = serializers.CharField()
    vendor_name = serializers.CharField()
    bus_or_package = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_amount = serializers.SerializerMethodField()
    payment_status = serializers.CharField()

    def get_balance_amount(self, obj):
        total_amount = obj.get('total_amount') or 0
        advance_amount = obj.get('advance_amount') or 0
        return total_amount - advance_amount




















class AmenitySerializerADMINBUSDETAILS(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name']


class BusFeatureSerializerADMINBUSDETAILS(serializers.ModelSerializer):
    class Meta:
        model = BusFeature
        fields = ['id', 'name']


class BusImageSerializerADMINBUSDETAILS(serializers.ModelSerializer):
    class Meta:
        model = BusImage
        fields = ['id', 'bus_view_image']


class BusTravelImageSerializerADMINBUSDETAILS(serializers.ModelSerializer):
    class Meta:
        model = BusTravelImage
        fields = ['id', 'image']


class VendorSerializerADMINBUSDETAILS(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            'full_name',
            'email_address',
            'phone_no',
            'travels_name',
            'location',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'district'
        ]


class BusAdminSerializerADMINBUSDETAILS(serializers.ModelSerializer):
    vendor = VendorSerializerADMINBUSDETAILS(read_only=True)
    amenities = AmenitySerializerADMINBUSDETAILS(many=True, read_only=True)
    features = BusFeatureSerializerADMINBUSDETAILS(many=True, read_only=True)
    images = BusImageSerializerADMINBUSDETAILS(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)

    class Meta:
        model = Bus
        fields = [
            'id', 'vendor', 'bus_name', 'bus_number', 'capacity',
            'vehicle_description', 'travels_logo',
            'rc_certificate', 'license', 'contract_carriage_permit',
            'passenger_insurance', 'vehicle_insurance',
            'amenities', 'features', 'base_price', 'price_per_km',
            'minimum_fare', 'status', 'location', 'latitude', 'longitude',
            'bus_type', 'is_popular', 'average_rating', 'total_reviews',
            'images',
        ]






class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'mobile', 'email', 'password', 'role']



    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user





class BusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = BusReview
        fields = ['id', 'user_name', 'bus', 'rating', 'comment', 'created_at']

    def get_user_name(self,obj):
        return obj.user.name

class PackageReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = PackageReview
        fields = ['id', 'user_name', 'package', 'rating', 'comment', 'created_at']

    def get_user_name(self,obj):
        return obj.user.name

class AppReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AppReview
        fields = ['id', 'user_name', 'rating', 'comment', 'created_at']

    def get_user_name(self,obj):
        return obj.user.name





class UnifiedReviewSerializer(serializers.Serializer):
    user = serializers.CharField()
    rating = serializers.FloatField()
    comment = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    type = serializers.CharField()
    related_name = serializers.CharField()


















# serializers.py
from rest_framework import serializers
from users.models import ReferralRewardTransaction

class ReferralRewardListSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='referrer.name')
    refer_id = serializers.SerializerMethodField()
    status_text = serializers.SerializerMethodField()
    
    class Meta:
        model = ReferralRewardTransaction
        fields = ['id', 'name', 'created_at', 'refer_id', 'reward_amount', 'status', 'status_text', 'booking_type']

    def get_refer_id(self, obj):
        return f"#{obj.id:08d}"

    def get_status_text(self, obj):
        if obj.status == 'pending':
            return 'Withdraw'
        elif obj.status == 'credited':
            return 'Completed'
        return obj.status.capitalize()


class ReferralRewardDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='referrer.name')
    refer_id = serializers.SerializerMethodField()

    class Meta:
        model = ReferralRewardTransaction
        fields = ['name', 'booking_id', 'created_at', 'refer_id', 'reward_amount', 'status']

    def get_refer_id(self, obj):
        return f"#{obj.id:08d}"






class AdminCreateBusSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(write_only=True)
    bus_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        min_length=1,
        help_text="At least one bus image is required"
    )

    class Meta:
        model = Bus
        fields = [
            'vendor_id',
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
            'base_price_km',
            'price_per_km',
            'night_allowance',
            'minimum_fare',
            'status',
            'location',
            'latitude',
            'longitude',
            'bus_type',
            'is_popular',
            'amenities',
            'features',
            'bus_images'
        ]

    def validate_vendor_id(self, value):
        try:
            Vendor.objects.get(pk=value)
        except Vendor.DoesNotExist:
            raise serializers.ValidationError("Vendor not found.")
        return value

    def validate_bus_images(self, value):
        if not value:
            raise serializers.ValidationError("At least one bus image is required.")
        
        for image in value:
            if image.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Image size should not exceed 5MB.")
        
        return value

    def create(self, validated_data):
        vendor_id = validated_data.pop('vendor_id')
        vendor = Vendor.objects.get(pk=vendor_id)

        amenities = validated_data.pop('amenities', [])
        features = validated_data.pop('features', [])
        bus_images = validated_data.pop('bus_images', [])

        bus = Bus.objects.create(vendor=vendor, **validated_data)

        bus.amenities.set(amenities)
        bus.features.set(features)

        for image in bus_images:
            BusImage.objects.create(bus=bus, bus_view_image=image)

        return bus
    





class AdminEditBusSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(write_only=True, required=False)
    bus_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        help_text="Upload new bus images (will replace existing images)"
    )
    remove_image_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of image IDs to remove"
    )

    class Meta:
        model = Bus
        fields = [
            'vendor_id',
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
            'base_price_km',
            'price_per_km',
            'night_allowance',
            'minimum_fare',
            'status',
            'location',
            'latitude',
            'longitude',
            'bus_type',
            'is_popular',
            'amenities',
            'features',
            'bus_images',
            'remove_image_ids'
        ]

    def validate_vendor_id(self, value):
        try:
            Vendor.objects.get(pk=value)
        except Vendor.DoesNotExist:
            raise serializers.ValidationError("Vendor not found.")
        return value

    def validate_bus_images(self, value):
        if value:
            for image in value:
                if image.size > 5 * 1024 * 1024:
                    raise serializers.ValidationError("Image size should not exceed 5MB.")
        return value

    def validate_remove_image_ids(self, value):
        if value:
            existing_ids = BusImage.objects.filter(
                bus=self.instance,
                id__in=value
            ).values_list('id', flat=True)
            
            invalid_ids = set(value) - set(existing_ids)
            if invalid_ids:
                raise serializers.ValidationError(f"Invalid image IDs: {list(invalid_ids)}")
        return value

    def update(self, instance, validated_data):
        vendor_id = validated_data.pop('vendor_id', None)
        amenities = validated_data.pop('amenities', None)
        features = validated_data.pop('features', None)
        bus_images = validated_data.pop('bus_images', None)
        remove_image_ids = validated_data.pop('remove_image_ids', None)

        # Update vendor if provided
        if vendor_id:
            vendor = Vendor.objects.get(pk=vendor_id)
            instance.vendor = vendor

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update amenities if provided
        if amenities is not None:
            instance.amenities.set(amenities)

        # Update features if provided
        if features is not None:
            instance.features.set(features)

        # Remove specified images
        if remove_image_ids:
            BusImage.objects.filter(bus=instance, id__in=remove_image_ids).delete()

        # Add new images
        if bus_images:
            for image in bus_images:
                BusImage.objects.create(bus=instance, bus_view_image=image)

        return instance


class AdminPackageBasicSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(write_only=True)
    bus_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of bus IDs to associate with this package"
    )
    buses = serializers.PrimaryKeyRelatedField(
        queryset=Bus.objects.all(),
        many=True
    )
    package_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True
    )

    # Optional Fields
    bus_location = serializers.CharField(required=False, allow_blank=True)
    price_per_person = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    extra_charge_per_km = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = Package
        fields = [
            'id',
            'vendor_id',
            'sub_category',
            'header_image',
            'places',
            'days',
            'ac_available',
            'guide_included',
            'bus_ids',
            'buses',
            'package_images',
            'bus_location',
            'price_per_person',
            'extra_charge_per_km',
            'status',
        ]

    def validate_vendor_id(self, value):
        if not Vendor.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Vendor not found.")
        return value

    def validate_bus_ids(self, value):
        if value:
            existing_buses = Bus.objects.filter(id__in=value)
            if existing_buses.count() != len(value):
                existing_ids = list(existing_buses.values_list('id', flat=True))
                invalid_ids = set(value) - set(existing_ids)
                raise serializers.ValidationError(f"Invalid bus IDs: {list(invalid_ids)}")
        return value

    def validate_header_image(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Header image size should not exceed 5MB.")
        return value

    def create(self, validated_data):
        vendor_id = validated_data.pop('vendor_id')
        vendor = Vendor.objects.get(pk=vendor_id)

        bus_ids = validated_data.pop('bus_ids', [])
        buses = validated_data.pop('buses', [])
        images = validated_data.pop('package_images', [])

        package = Package.objects.create(vendor=vendor, **validated_data)

        if bus_ids:
            bus_objs = Bus.objects.filter(id__in=bus_ids)
            package.buses.set(bus_objs)
        elif buses:
            package.buses.set(buses)

        for img in images:
            PackageImage.objects.create(package=package, image=img)

        return package


class AdminEditPackageSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(write_only=True, required=False)
    bus_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of bus IDs to associate with this package"
    )

    class Meta:
        model = Package
        fields = [
            'vendor_id',
            'sub_category',
            'header_image',
            'places',
            'days',
            'ac_available',
            'guide_included',
            'bus_ids',
            'bus_location',
            'price_per_person',
            'extra_charge_per_km',
            'status'
        ]

    def validate_vendor_id(self, value):
        try:
            Vendor.objects.get(pk=value)
        except Vendor.DoesNotExist:
            raise serializers.ValidationError("Vendor not found.")
        return value

    def validate_bus_ids(self, value):
        if value:
            existing_buses = Bus.objects.filter(id__in=value)
            if existing_buses.count() != len(value):
                existing_ids = list(existing_buses.values_list('id', flat=True))
                invalid_ids = set(value) - set(existing_ids)
                raise serializers.ValidationError(f"Invalid bus IDs: {list(invalid_ids)}")
        return value

    def validate_header_image(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Header image size should not exceed 5MB.")
        return value

    def update(self, instance, validated_data):
        vendor_id = validated_data.pop('vendor_id', None)
        bus_ids = validated_data.pop('bus_ids', None)

        if vendor_id:
            vendor = Vendor.objects.get(pk=vendor_id)
            instance.vendor = vendor

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if bus_ids is not None:
            buses = Bus.objects.filter(id__in=bus_ids)
            instance.buses.set(buses)

        return instance
    



class BusImageDeleteSerializer(serializers.Serializer):
    image_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of image IDs to delete"
    )

    def validate_image_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one image ID is required.")
        
        existing_ids = BusImage.objects.filter(id__in=value).values_list('id', flat=True)
        invalid_ids = set(value) - set(existing_ids)
        
        if invalid_ids:
            raise serializers.ValidationError(f"Invalid image IDs: {list(invalid_ids)}")
        
        return value