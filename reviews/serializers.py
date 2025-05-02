from rest_framework import serializers
from .models import BusReview

class BusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    
    class Meta:
        model = BusReview
        fields = ["id", "user", "bus", "user_name", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            'user': {'write_only': True},
        }
