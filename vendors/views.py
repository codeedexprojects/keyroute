from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import VendorSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import *
from django.core.mail import send_mail
from .serializers import *
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser

from admin_panel.models import *

# Create your views here.

# VENDOR REGISTRATION
class VendorSignupAPIView(APIView):
 
    def post(self, request):
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Vendor registered successfully!", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
# VEONDOR LOGIN
class LoginAPIView(APIView):
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {"errors": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"errors": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful!",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)






# VENDOR LOGOUT
class LogoutAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print('logout is working')
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out!"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)





# OTP CREATION
class SendOtpAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        print(email,'email')

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vendor = Vendor.objects.get(email_address=email)

            otp_instance, _ = OTP.objects.get_or_create(user=vendor.user)
            otp = otp_instance.generate_otp()

            subject = "Your OTP for Password Reset"
            message = f"Your OTP code is {otp}. It is valid for 5 minutes."
            from_email = "praveen.codeedex@gmail.com"   
            recipient_list = [email]

            send_mail(subject, message, from_email, recipient_list)

            return Response({"message": "OTP sent successfully! Please check your email."}, status=status.HTTP_200_OK)

        except Vendor.DoesNotExist:
            return Response({"error": "Vendor with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)


# OTP VERIFCATION
class VerifyOtpAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        if not email or not otp:
            return Response({"error": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vendor = Vendor.objects.get(email_address=email)
            otp_instance = OTP.objects.get(user=vendor.user)

            if otp_instance.otp_code != otp:
                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

            if not otp_instance.is_valid():
                return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "OTP verified! You can now reset your password."}, status=status.HTTP_200_OK)

        except (Vendor.DoesNotExist, OTP.DoesNotExist):
            return Response({"error": "Invalid email or OTP."}, status=status.HTTP_404_NOT_FOUND)


# RESET PASSWORD
class ResetPasswordAPIView(APIView):
    def post(self, request):

        email = request.data.get('email')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not all([email, new_password, confirm_password]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vendor = Vendor.objects.get(email_address=email)
            user = vendor.user
            user.set_password(new_password)
            user.save()

            OTP.objects.filter(user=user).delete()

            return Response({"message": "Password updated successfully!"}, status=status.HTTP_200_OK)

        except Vendor.DoesNotExist:
            return Response({"error": "Vendor with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)






# BUS CREATION AND LIST 
class BusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            buses = Bus.objects.filter(vendor=vendor)
            serializer = BusSerializer(buses, many=True)
            return Response({"buses": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            serializer = BusSerializer(data=request.data, context={'vendor': vendor})
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Bus created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# BUS EDIT  AND DELETE
class BusEditAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def put(self, request, bus_id):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            try:
                bus = Bus.objects.get(id=bus_id, vendor=vendor)
            except Bus.DoesNotExist:
                return Response({"error": "Bus not found or unauthorized access."}, status=status.HTTP_404_NOT_FOUND)

            serializer = BusSerializer(bus, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Bus updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

    
    def delete(self, request, bus_id):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            try:
                bus = Bus.objects.get(id=bus_id, vendor=vendor)
                bus.delete()
                return Response({"message": "Bus deleted successfully!"}, status=status.HTTP_200_OK)
            except Bus.DoesNotExist:
                return Response({"error": "Bus not found or unauthorized access."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




# PACKAGE CATEGORY CREATED AND LISTED
class PackageCategoryAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser,JSONParser]

    def post(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user) 


        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data["vendor"] = vendor.user_id

        serializer = PackageCategorySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Package Category created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

        categories = PackageCategory.objects.filter(vendor=vendor)
        serializer = PackageCategorySerializer(categories, many=True)

        return Response({"message": "Package categories fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)
    

    def patch(self, request, pk):
        try:
            vendor = Vendor.objects.get(user=request.user)
            category = PackageCategory.objects.get(id=pk, vendor=vendor)
        except (Vendor.DoesNotExist, PackageCategory.DoesNotExist):
            return Response({"error": "Package Category not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageCategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Package Category updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request, pk):
        try:
            vendor = Vendor.objects.get(user=request.user)
            category = PackageCategory.objects.get(id=pk, vendor=vendor)
        except (Vendor.DoesNotExist, PackageCategory.DoesNotExist):
            return Response({"error": "Package Category not found."}, status=status.HTTP_404_NOT_FOUND)

        category.delete()
        return Response({"message": "Package Category deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)





class PackageSubCategoryAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  

    def get_vendor(self, request):
        return Vendor.objects.filter(user=request.user).first()

    def get_object(self, pk):
        try:
            return PackageSubCategory.objects.get(pk=pk)
        except PackageSubCategory.DoesNotExist:
            return None

    def post(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        
        try:
            category = PackageCategory.objects.get(id=data["category"], vendor=vendor)
        except PackageCategory.DoesNotExist:
            return Response({"error": "Invalid category for this vendor."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PackageSubCategorySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Package SubCategory created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def get(self, request, pk=None):
        if pk:
            subcategory = self.get_object(pk)
            if not subcategory:
                return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = PackageSubCategorySerializer(subcategory)
            return Response({"subcategory": serializer.data}, status=status.HTTP_200_OK)

        subcategories = PackageSubCategory.objects.all()
        serializer = PackageSubCategorySerializer(subcategories, many=True)
        return Response({"subcategories": serializer.data}, status=status.HTTP_200_OK)

    def put(self, request, pk):
        subcategory = self.get_object(pk)
        if not subcategory:
            return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageSubCategorySerializer(subcategory, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "SubCategory updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        subcategory = self.get_object(pk)
        if not subcategory:
            return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

        subcategory.delete()
        return Response({"message": "SubCategory deleted successfully!"}, status=status.HTTP_200_OK)







