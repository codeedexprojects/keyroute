from rest_framework import serializers
from .models import BusReview, PackageReview,AppReview
from django.db.models import Avg

class BusReviewSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    
    class Meta:
        model = BusReview
        fields = ["user",'profile_image',"bus","rating", "comment", "created_at"]

    def get_user(self, obj):
        return obj.user.name if obj.user.name else obj.user.email
    
    def get_profile_image(self, obj):
        if obj.user.profile_image:
            return obj.user.profile_image.url
        return None


class PackageReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    user_profile_image = serializers.ImageField(source="user.profile_image", read_only=True)
    name = serializers.CharField(source='package.places', read_only=True)
    
    class Meta:
        model = PackageReview
        fields = ["id", "user", "package", "user_name", "rating", "comment", "created_at", "created_at_formatted",'user_profile_image','name']
        read_only_fields = ["id", "created_at", "created_at_formatted"]
        extra_kwargs = {
            'user': {'write_only': True},
        }

    def get_user_profile_image(self, obj):
        if obj.user.profile_image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.user.profile_image.url) if request else obj.user.profile_image.url
        return None
    
    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime("%B %d, %Y")


class BusReviewSummarySerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    rating_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = BusReview
        fields = ["average_rating", "total_reviews", "rating_breakdown"]
    
    def get_average_rating(self, obj):
        return obj.bus_reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    
    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()
    
    def get_rating_breakdown(self, obj):
        breakdown = {}
        for i in range(1, 6):
            breakdown[f"{i}★"] = obj.bus_reviews.filter(rating=i).count()
        return breakdown


class PackageReviewSummarySerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    rating_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = PackageReview
        fields = ["average_rating", "total_reviews", "rating_breakdown"]
    
    def get_average_rating(self, obj):
        return obj.package_reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    
    def get_total_reviews(self, obj):
        return obj.package_reviews.count()
    
    def get_rating_breakdown(self, obj):
        breakdown = {}
        for i in range(1, 6):
            breakdown[f"{i}★"] = obj.package_reviews.filter(rating=i).count()
        return breakdown
    

class AppReviewSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    
    class Meta:
        model = AppReview
        fields = ['id', 'user', 'username', 'rating', 'comment', 'created_at']
        read_only_fields = ['user', 'created_at']
    
    def get_username(self, obj):
        return obj.user.name if obj.user.name else obj.user.email
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ReviewStatsSerializer(serializers.Serializer):
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField()
    reviews = AppReviewSerializer(many=True)