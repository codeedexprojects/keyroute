from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_panel.models import Vendor
from admin_panel.serializers import VendorSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from admin_panel.models import User
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import *
from vendors.models import *
from vendors.serializers import *


# Create your views here.


class AdminLoginAPIView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if user is not None and user.role == User.ADMIN:
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Admin login successful!",
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid credentials or not an admin."}, status=status.HTTP_401_UNAUTHORIZED)



# ALL VENDORS LIST
class VendorListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)

        vendors = Vendor.objects.all()
        serializer = VendorSerializer(vendors, many=True)
        return Response({"vendors": serializer.data}, status=status.HTTP_200_OK)



class VendorDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, vendor_id):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)

        try:
            vendor = Vendor.objects.get(pk=vendor_id)
            serializer = VendorSerializer(vendor)
            return Response({"vendor": serializer.data}, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)


# TOTTEL VENDORS COUNT
class VendorCountAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)

        vendor_count = Vendor.objects.count()
        return Response({"total_vendors": vendor_count}, status=status.HTTP_200_OK)
    


class UserCountAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)

        user_count = User.objects.filter(role=User.USER).count()

        data = {
            "user_count": user_count,
        }

        return Response(data, status=status.HTTP_200_OK)



# RECENT USERS
class RecentlyJoinedUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)
        
        recent_users = User.objects.filter(role=User.USER).order_by('-date_joined')[:5]
        serializer = UserSerializer(recent_users, many=True)
        return Response({"recent_users": serializer.data}, status=status.HTTP_200_OK)




class AdminBusListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if request.user.role != User.ADMIN:
            return Response(
                {"error": "Unauthorized access. Only admins can view this data."},
                status=status.HTTP_403_FORBIDDEN
            )

        buses = Bus.objects.all()
        serializer = BusSerializer(buses, many=True)

        return Response({
            "message": "List of all buses",
            "buses": serializer.data
        }, status=status.HTTP_200_OK)





