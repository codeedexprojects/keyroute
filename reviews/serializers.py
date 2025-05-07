from rest_framework import serializers
from .models import BusReview, PackageReview
from django.db.models import Avg

class BusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    user_profile_image = serializers.ImageField(source="user.profile_image", read_only=True)
    
    class Meta:
        model = BusReview
        fields = ["id", "user", "bus", "user_name", "rating", "comment", "created_at", "created_at_formatted",'user_profile_image']
        read_only_fields = ["id", "created_at", "created_at_formatted"]
        extra_kwargs = {
            'user': {'write_only': True},
        }
    
    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime("%B %d, %Y")


class PackageReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    user_profile_image = serializers.ImageField(source="user.profile_image", read_only=True)
    
    class Meta:
        model = PackageReview
        fields = ["id", "user", "package", "user_name", "rating", "comment", "created_at", "created_at_formatted",'user_profile_image']
        read_only_fields = ["id", "created_at", "created_at_formatted"]
        extra_kwargs = {
            'user': {'write_only': True},
        }
    
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