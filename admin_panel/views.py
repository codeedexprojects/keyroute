from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_panel.models import Vendor
from admin_panel.serializers import VendorSerializer1
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from admin_panel.models import User
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import *
from vendors.models import *
from vendors.serializers import *
from django.db.models import Q


# Create your views here.




class AdminLoginAPIView(APIView):
    def post(self, request):
        identifier = request.data.get('email_or_phone')   
        password = request.data.get('password')

        if not identifier or not password:
            return Response({"error": "Email/Phone and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(Q(email=identifier) | Q(mobile=identifier))
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if user.role != User.ADMIN:
            return Response({"error": "Unauthorized access. Only admins can log in."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Admin login successful!",
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, status=status.HTTP_200_OK)

# ALL VENDORS LIST
class VendorListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)

        vendors = Vendor.objects.all()
        serializer = VendorSerializer1(vendors, many=True)
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







class AllUsersAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            try:
                user = User.objects.get(id=user_id, role=User.USER)
                serializer = UserSerializer(user)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User not found or not a normal user."}, status=status.HTTP_404_NOT_FOUND)
        else:
            users = User.objects.filter(role=User.USER)
            serializer = UserSerializer(users, many=True)
            return Response({
                "total_users": users.count(),
                "users": serializer.data
            }, status=status.HTTP_200_OK)



# VENDOR CREATING AND LISTING
class AdminCreateVendorAPIView(APIView):
    def post(self, request):
        serializer = AdminVendorSerializer(data=request.data)
        if serializer.is_valid():
            vendor = serializer.save()
            return Response({
                "message": "Vendor created successfully by admin",
                "data": AdminVendorSerializer(vendor).data
            }, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    


    def get(self, request):
        vendors = Vendor.objects.all()
        serializer = VendorFullSerializer(vendors, many=True)
        return Response({
            "message": "List of all vendors",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


# VENDOR DETAILS
class AdminVendorDetailAPIView(APIView):
    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = VendorFullSerializer(vendor)
        return Response({
            "message": "Vendor details retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


# ADMIN BUS LISTING
class AdminVendorBusListAPIView(APIView):
    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

        buses = vendor.bus_set.all()
        serializer = BusSerializer(buses, many=True)
        return Response({
            "message": "Bus list retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)




# ADMIN BUS DETAILS
class AdminBusDetailAPIView(APIView):
    def get(self, request, bus_id):
        try:
            bus = Bus.objects.get(pk=bus_id)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = BusDetailSerializer(bus)
        return Response({
            "message": "Bus details retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    




# VENDOR PACKAGE LISTING
class AdminVendorPackageListAPIView(APIView):
    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(user=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

        packages = vendor.package_set.all()
        serializer = AdminPackageListSerializer(packages, many=True)
        return Response({
            "message": "Package list retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

# VENDOR PACKAGE DETAILS
class AdminPackageDetailAPIView(APIView):
    def get(self, request, package_id):
        try:
            package = Package.objects.get(pk=package_id)
        except Package.DoesNotExist:
            return Response({"error": "Package not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPackageDetailSerializer(package)
        return Response({
            "message": "Package details retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)