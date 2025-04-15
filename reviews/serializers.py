from rest_framework import serializers
from .models import BusReview

class BusReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = BusReview
        fields = ["user_name", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at"]