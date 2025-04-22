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
from django.db.models import Q
import json
from collections import defaultdict
import re
from django.shortcuts import get_object_or_404
from django.db.models.functions import TruncMonth
from django.db.models import Sum
from datetime import datetime, timedelta
from bookings.models import *
from django.db.models import Sum, Count, F
from django.utils.timezone import now

from admin_panel.models import *

# Create your views here.

# VENDOR REGISTRATION
class VendorSignupAPIView(APIView):
    def post(self, request):
        print(request.data,'data')
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            vendor = serializer.save()
            return Response(
                {"message": "Vendor registered successfully!", "data": VendorSerializer(vendor).data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    
# # VEONDOR LOGIN
class LoginAPIView(APIView):

    def post(self, request):
        identifier = request.data.get('email_or_phone')   
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {"errors": "Mobile number or email and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(Q(mobile=identifier) | Q(email=identifier))
        except User.DoesNotExist:
            return Response(
                {"errors": "Invalid credentials."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(password):
            return Response(
                {"errors": "Invalid credentials."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.role != User.VENDOR:
            return Response(
                {"errors": "Unauthorized access. Only vendors can log in."},
                status=status.HTTP_403_FORBIDDEN
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
                bus = serializer.save()
                VendorNotification.objects.create(
                    vendor=vendor,
                    description=f"Your bus '{bus.bus_name}' has been created successfully!"
                )
                return Response({"message": "Bus created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# BUS EDIT  AND DELETE
class BusEditAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]



    def get(self, request, bus_id):
        """Retrieve a single bus by ID if it belongs to the authenticated vendor."""
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            try:
                bus = Bus.objects.get(id=bus_id, vendor=vendor)
                serializer = BusSerializer(bus)
                return Response({"data": serializer.data}, status=status.HTTP_200_OK)
            except Bus.DoesNotExist:
                return Response({"error": "Bus not found or unauthorized access."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        
        
    def patch(self, request, bus_id):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            try:
                bus = Bus.objects.get(id=bus_id, vendor=vendor)
            except Bus.DoesNotExist:
                return Response({"error": "Bus not found or unauthorized access."}, status=status.HTTP_404_NOT_FOUND)

            serializer = BusSerializer(bus, data=request.data, partial=True, context={'vendor': vendor})
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





class AmenityCreateAPIView(APIView):

    def get(self, request):
        amenities = Amenity.objects.all()
        serializer = AmenitySerializer(amenities, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AmenitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Amenity created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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










# PACKAGE CRUD
class PackageAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]  
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 

    def post(self, request):
        data = request.data.dict()   
        files = request.FILES   


        day_plans = data.get('day_plans')
        if day_plans and isinstance(day_plans, str):
            try:
                data['day_plans'] = json.loads(day_plans)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format for day_plans"}, status=400)

        
        print(files,'files')

        image_fields = defaultdict(list)

        for key, file in files.items():
            key_parts = key.split('_')
            if len(key_parts) >= 4:
                model_type = key_parts[0]       
                index = int(key_parts[1])       
                image_index = int(key_parts[3]) 
                image_fields[(model_type, index)].append({"image": file})

        for day_plan in data['day_plans']:
            for model_type in ['places', 'meals', 'activities']:
                if model_type in day_plan:
                    for idx, item in enumerate(day_plan[model_type]):
                        item['images'] = image_fields.get((model_type, idx), [])

            if 'stay' in day_plan:
                day_plan['stay']['images'] = image_fields.get(('stay', 0), [])

        buses_raw = request.data.getlist('buses')

        if len(buses_raw) == 1:
            try:
                buses_list = json.loads(buses_raw[0])
                if isinstance(buses_list, list):
                    data['buses'] = [int(b) for b in buses_list]
                else:
                    data['buses'] = [int(buses_raw[0])]
            except (ValueError, json.JSONDecodeError):
                data['buses'] = [int(buses_raw[0])]
        else:
            data['buses'] = [int(b) for b in buses_raw]



        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
            print('started')

            serializer = PackageSerializer(data=data, context={"vendor": vendor})
            print('second')
            if serializer.is_valid():
                package = serializer.save()
                VendorNotification.objects.create(
                    vendor=vendor,
                    description=f"Your package '{package.places}' has been successfully created."
                )
                return Response({
                    "message": "Package created successfully.",
                    "data": PackageSerializer(package).data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




    def get(self, request, package_id=None):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        if package_id:
            package = get_object_or_404(Package, pk=package_id, vendor=vendor)
            serializer = PackageReadSerializer(package)
            return Response(serializer.data, status=status.HTTP_200_OK)

        packages = Package.objects.filter(vendor=vendor).prefetch_related(
            'day_plans__places__images',
            'day_plans__stay__images',
            'day_plans__meals__images',
            'day_plans__activities__images',
            'buses'
        )
        serializer = PackageReadSerializer(packages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, package_id):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        package = get_object_or_404(Package, pk=package_id, vendor=vendor)

        data = request.data.dict()
        files = request.FILES

        day_plans = data.get('day_plans')
        if day_plans and isinstance(day_plans, str):
            try:
                data['day_plans'] = json.loads(day_plans)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format for day_plans"}, status=400)

        buses_raw = request.data.getlist('buses')
        if buses_raw:
            if len(buses_raw) == 1:
                try:
                    buses_list = json.loads(buses_raw[0])
                    data['buses'] = [int(b) for b in buses_list] if isinstance(buses_list, list) else [int(buses_raw[0])]
                except (ValueError, json.JSONDecodeError):
                    data['buses'] = [int(buses_raw[0])]
            else:
                data['buses'] = [int(b) for b in buses_raw]

        serializer = PackageSerializerPUT(package, data=data, context={"vendor": vendor}, partial=True)
        if serializer.is_valid():
            updated_package = serializer.save()
            return Response({
                "message": "Package updated successfully.",
                "data": PackageSerializer(updated_package).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, package_id):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        package = get_object_or_404(Package, pk=package_id, vendor=vendor)
        package.delete()
        return Response({"message": "Package deleted successfully."}, status=status.HTTP_204_NO_CONTENT)












class VendorProfileAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
            serializer = VendorSerializer(vendor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor profile not found."}, status=status.HTTP_404_NOT_FOUND)


    def patch(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
            serializer = VendorSerializer(vendor, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Vendor profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor profile not found."}, status=status.HTTP_404_NOT_FOUND)



class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not user.check_password(current_password):
            return Response({"error": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "New password and confirm password do not match."}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({"error": "New password must be at least 6 characters long."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password updated successfully!"}, status=status.HTTP_200_OK)








class VendorBankDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        vendor = get_object_or_404(Vendor, user=request.user)
        serializer = VendorBankDetailSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(vendor=vendor)
            return Response({"message": "Bank details created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
    

    def post(self, request):
        vendor = get_object_or_404(Vendor, user=request.user)

        if VendorBankDetail.objects.filter(vendor=vendor).exists():
            return Response(
                {"message": "Bank details already exist for this vendor."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VendorBankDetailSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(vendor=vendor)
            return Response(
                {
                    "message": "Bank details created successfully.",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        try:
            bank_detail = VendorBankDetail.objects.get(vendor=request.user.vendor)
            serializer = VendorBankDetailSerializer(bank_detail)
            return Response({
                "message": "Bank details fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except VendorBankDetail.DoesNotExist:
            return Response({
                "message": "Bank details not found"
            }, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        vendor = get_object_or_404(Vendor, user=request.user)
        try:
            bank_detail = vendor.bank_detail   
        except VendorBankDetail.DoesNotExist:
            return Response({"error": "Bank details not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = VendorBankDetailSerializer(bank_detail, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Bank details updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class BusFeatureCreateAPIView(APIView):
    def post(self, request):
        serializer = BusFeatureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def get(self, request):
        features = BusFeature.objects.all()
        serializer = BusFeatureSerializer(features, many=True) 
        return Response(serializer.data, status=status.HTTP_200_OK)


         


class VendorNotificationListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        notifications = VendorNotification.objects.filter(vendor=vendor).order_by('-created_at')
        serializer = VendorNotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class MarkNotificationAsReadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            notification = VendorNotification.objects.get(id=notification_id, vendor=vendor)
            notification.is_read = True
            notification.save()
            return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)
        except VendorNotification.DoesNotExist:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)














# ------------------------------------HOME PAGE-----------------



class VendorTotalRevenueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=404)

        today = datetime.today()
        five_months_ago = today.replace(day=1) - timedelta(days=150)

        bus_revenue = BusBooking.objects.filter(
            bus__vendor=vendor,
            created_at__gte=five_months_ago,
            payment_status__in=["paid", "partial"]
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        package_revenue = PackageBooking.objects.filter(
            package__vendor=vendor,
            created_at__gte=five_months_ago,
            payment_status__in=["paid", "partial"]
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        total_revenue = float(bus_revenue) + float(package_revenue)

        return Response({
            "total_revenue_last_5_months": total_revenue
        }, status=200)








class BusBookingRevenueListView(APIView):
    def get(self, request):
        today = datetime.today()
        current_month = today.month
        current_year = today.year

        next_month = today.replace(day=28) + timedelta(days=4)

        monthly_revenue = BusBooking.objects.filter(
            created_at__month=current_month,
            created_at__year=current_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        queryset = BusBooking.objects.values(
            'bus_id',
            'from_location',
            'to_location',
            bus_name=F('bus__bus_name')
        ).annotate(
            total_bookings=Count('id'),
            total_revenue=Sum('total_amount'),
            total_advance_paid=Sum('advance_amount'),
            total_balance_due=Sum(F('total_amount') - F('advance_amount')),
            total_travelers=Count('travelers__id'),
        )

        serializer = BusBookingRevenueSerializer(queryset, many=True)

        return Response({
            "total_monthly_revenue": monthly_revenue,
            
            "data": serializer.data
        })








class PackageBookingRevenueListView(APIView):
    def get(self, request):
        today = datetime.today()
        current_month = today.month
        current_year = today.year


        monthly_revenue = PackageBooking.objects.filter(
            created_at__month=current_month,
            created_at__year=current_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        queryset = PackageBooking.objects.values(
            'package_id',
            package_places=F('package__places'),
        ).annotate(
            total_bookings=Count('id'),
            total_revenue=Sum('total_amount'),
            total_advance_paid=Sum('advance_amount'),
            total_balance_due=Sum(F('total_amount') - F('advance_amount')),
            total_travelers=Count('travelers__id'),
        )

        serializer = PackageBookingRevenueSerializer(queryset, many=True)
        return Response({
            "total_monthly_revenue": monthly_revenue,
            "data": serializer.data
        })






class BusBookingLatestView(APIView):
    def get(self, request):
        latest_bookings = BusBooking.objects.all().order_by('-created_at')[:5]   

        serializer = BusBookingLatestSerializer(latest_bookings, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)




class BusBookingDetailView(APIView):
    """API View to get full details of a single bus booking"""

    def get(self, request, booking_id, format=None):
        try:
            # Fetch the bus booking by ID
            booking = BusBooking.objects.get(id=booking_id)
        except BusBooking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BusBookingDetailSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)





class LatestPackageBookingDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


    def get(self, request, format=None):
        user = request.user
        print(user)

        latest_booking = PackageBooking.objects.filter(user=user).order_by('-id').first()
        
        if not latest_booking:
            return Response({"message": "No package bookings found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageBookingDetailSerializer(latest_booking)
        return Response(serializer.data, status=status.HTTP_200_OK)
    





class BusBookingBasicHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = request.user.vendor   

        vendor_buses = Bus.objects.filter(vendor=vendor)

        # Get bookings where the bus is in vendor_buses
        bookings = BusBooking.objects.filter(bus__in=vendor_buses).order_by('-start_date')

        serializer = BusBookingBasicSerializer(bookings, many=True)
        return Response({"history": serializer.data})





class SingleBusBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            print('is working')
            vendor = request.user.vendor
            booking = BusBooking.objects.select_related('bus', 'user').prefetch_related('travelers').get(
                id=booking_id, bus__vendor=vendor
            )
            serializer = BusBookingDetailSerializer(booking)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except BusBooking.DoesNotExist:
            return Response({"error": "Booking not found or not authorized."}, status=status.HTTP_404_NOT_FOUND)







class PackageBookingBasicHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        package_bookings = PackageBooking.objects.filter(user=request.user).order_by('-start_date')
        serializer = PackageBookingBasicSerializer(package_bookings, many=True)
        return Response({"history": serializer.data})



class SinglePackageBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            package_booking = PackageBooking.objects.get(id=booking_id, user=request.user)
        except PackageBooking.DoesNotExist:
            return Response({"error": "Package booking not found"}, status=404)
        
        serializer = PackageBookingDetailSerializer(package_booking)
        return Response({"package_booking_details": serializer.data})



