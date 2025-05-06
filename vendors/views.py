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
from .serializers import PackageBasicSerializer
from admin_panel.models import *
from calendar import monthrange

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
        vendor_name = ""
        try:
            vendor_name = user.vendor.full_name
            travels_name= user.vendor.travels_name
        except Vendor.DoesNotExist:
            pass
        return Response({
            "message": "Login successful!",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "vendor_name": vendor_name,
            "travels_name":travels_name
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
        print('this work')
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            buses = Bus.objects.filter(vendor=vendor)
            serializer = BusSerializer(buses, many=True)
            # serializer = BusSummarySerializer(buses, many=True)
            return Response({"buses": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

  

    def post(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            data = request.data.copy()

            def parse_list_field(key):
                raw = data.get(key)
                if raw:
                    try:
                        return json.loads(raw)
                    except (TypeError, ValueError):
                        return [int(x) for x in raw.strip("[]").replace("'", "").split(',') if x]
                return []

            amenities_ids = parse_list_field('amenities')
            features_ids = parse_list_field('features')

            data.pop('amenities', None)
            data.pop('features', None)

            serializer = BusSerializer(data=data, context={'vendor': vendor})


            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            bus = serializer.save()
            bus.amenities.set(amenities_ids)
            bus.features.set(features_ids)

            VendorNotification.objects.create(
                vendor=vendor,
                description=f"Your bus '{bus.bus_name}' has been created successfully!"
            )

            return Response({"message": "Bus created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)

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

   
    def get(self, request):
       

        categories = PackageCategory.objects.all()
        serializer = PackageCategorySerializer(categories, many=True)

        return Response({"message": "Package categories fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)
    

 



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

    # def post(self, request):
    #     try:
    #         vendor = Vendor.objects.get(user=request.user)
    #     except Vendor.DoesNotExist:
    #         return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

    #     data = request.data.copy()
        
    #     try:
    #         category = PackageCategory.objects.get(id=data["category"], vendor=vendor)
    #     except PackageCategory.DoesNotExist:
    #         return Response({"error": "Invalid category for this vendor."}, status=status.HTTP_400_BAD_REQUEST)

    #     serializer = PackageSubCategorySerializer(data=data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({"message": "Package SubCategory created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

    # def put(self, request, pk):
    #     subcategory = self.get_object(pk)
    #     if not subcategory:
    #         return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

    #     serializer = PackageSubCategorySerializer(subcategory, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({"message": "SubCategory updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # def delete(self, request, pk):
    #     subcategory = self.get_object(pk)
    #     if not subcategory:
    #         return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

    #     subcategory.delete()
    #     return Response({"message": "SubCategory deleted successfully!"}, status=status.HTTP_200_OK)










# PACKAGE CRUD
class PackageAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]  
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 

  
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





class BasicPackageAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            data = request.data.dict()
            buses_raw = request.data.getlist('buses')

            if len(buses_raw) == 1:
                try:
                    buses_list = json.loads(buses_raw[0])
                    data['buses'] = [int(b) for b in buses_list]
                except:
                    data['buses'] = [int(buses_raw[0])]
            else:
                data['buses'] = [int(b) for b in buses_raw]

            package_images = request.FILES.getlist('package_images')

            mutable_data = request.data.copy()
            mutable_data.setlist('package_images', package_images)
            mutable_data.setlist('buses', data['buses'])

            serializer = PackageBasicSerializer(data=mutable_data, context={'vendor': vendor})
            if serializer.is_valid():
                package = serializer.save()
                return Response({
                    "message": "Basic Package created successfully.",
                    "package_id": package.id
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# class DayPlanCreateAPIView(APIView):
#     parser_classes = [MultiPartParser, JSONParser]
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

  
    
#     def post(self, request, package_id):
#         try:
#             data = request.data.dict()
#             files = request.FILES

#             try:
#                 day_plans = json.loads(data.get("day_plans", "[]"))
#             except json.JSONDecodeError:
#                 return Response({"error": "Invalid day_plans JSON format"}, status=400)

#             grouped_images = defaultdict(list)
#             for key in files:
#                 parts = key.split('_')
#                 if parts[0] in ['places', 'meals', 'activities'] and len(parts) == 3:
#                     section, day_idx, item_idx = parts[0], int(parts[1][3:]), int(parts[2])
#                     grouped_images[(day_idx, section, item_idx)].extend(request.FILES.getlist(key))
#                 elif parts[0] == 'stay' and len(parts) == 2:
#                     day_idx = int(parts[1][3:])
#                     grouped_images[(day_idx, 'stay', 0)].extend(request.FILES.getlist(key))

#             print("\n--- DEBUG: Grouped Day Plans with Images ---")
#             for i, day in enumerate(day_plans):
#                 print(f"Day {i + 1}:")
#                 for section in ['places', 'meals', 'activities']:
#                     for idx, item in enumerate(day.get(section, [])):
#                         imgs = grouped_images.get((i, section, idx), [])
#                         item['images'] = [{"image": img} for img in imgs]
#                         print(f"  {section.capitalize()}[{idx}]: {item.get('name', '') or item.get('type', '')}")
#                         print(f"    Images: {[img.name for img in imgs]}")
#                 if 'stay' in day:
#                     imgs = grouped_images.get((i, 'stay', 0), [])
#                     day['stay']['images'] = [{"image": img} for img in imgs]
#                     print(f"  Stay:\n    Images: {[img.name for img in imgs]}")
#             print("--- End Debug ---\n")

#             package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
#             if not package:
#                 return Response({"error": "Package not found"}, status=404)

#             with transaction.atomic():
#                 for day in day_plans:
#                     places = day.pop("places", [])
#                     meals = day.pop("meals", [])
#                     activities = day.pop("activities", [])
#                     stay = day.pop("stay", None)

#                     day_instance = DayPlan.objects.create(package=package, **day)

#                     for place in places:
#                         images = place.pop("images", [])
#                         p = Place.objects.create(day_plan=day_instance, **place)
#                         for img in images:
#                             PlaceImage.objects.create(place=p, image=img["image"])

#                     if stay:
#                         images = stay.pop("images", [])
#                         s = Stay.objects.create(day_plan=day_instance, **stay)
#                         for img in images:
#                             StayImage.objects.create(stay=s, image=img["image"])

#                     for meal in meals:
#                         images = meal.pop("images", [])
#                         m = Meal.objects.create(day_plan=day_instance, **meal)
#                         for img in images:
#                             MealImage.objects.create(meal=m, image=img["image"])

#                     for activity in activities:
#                         images = activity.pop("images", [])
#                         a = Activity.objects.create(day_plan=day_instance, **activity)
#                         for img in images:
#                             ActivityImage.objects.create(activity=a, image=img["image"])

#             return Response({"message": "Day plans added successfully."}, status=201)

#         except Exception as e:
#             return Response({"error": str(e)}, status=500)


class DayPlanCreateAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, package_id):
        try:
            data = request.data.dict()
            files = request.FILES

            try:
                day_plans = json.loads(data.get("day_plans", "[]"))
            except json.JSONDecodeError:
                return Response({"error": "Invalid day_plans JSON format"}, status=400)

            grouped_images = defaultdict(list)
            for key in files:
                parts = key.split('_')
                if parts[0] in ['places', 'meals', 'activities'] and len(parts) == 3:
                    section, day_idx, item_idx = parts[0], int(parts[1][3:]), int(parts[2])
                    grouped_images[(day_idx, section, item_idx)].extend(request.FILES.getlist(key))
                elif parts[0] == 'stay' and len(parts) == 2:
                    day_idx = int(parts[1][3:])  # stay_day1
                    grouped_images[(day_idx, 'stay', 0)].extend(request.FILES.getlist(key))

            package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
            if not package:
                return Response({"error": "Package not found"}, status=404)

            with transaction.atomic():
                for idx, day in enumerate(day_plans):
                    places = day.pop("places", [])
                    meals = day.pop("meals", [])
                    activities = day.pop("activities", [])
                    stay = day.pop("stay", None)

                    day_instance = DayPlan.objects.create(package=package, **day)

                    for p_idx, place in enumerate(places):
                        images = place.pop("images", [])
                        p = Place.objects.create(day_plan=day_instance, **place)
                        for img in grouped_images.get((idx, 'places', p_idx), []):
                            PlaceImage.objects.create(place=p, image=img)

                    if stay:
                        images = stay.pop("images", [])
                        stay_fields = {
                            "hotel_name": stay.get("hotel_name"),
                            "description": stay.get("description"),
                            "location": stay.get("location"),
                            "is_ac": stay.get("ac", False),
                            "has_breakfast": stay.get("breakfast", False),
                        }
                        s = Stay.objects.create(day_plan=day_instance, **stay_fields)
                        for img in grouped_images.get((idx, 'stay', 0), []):
                            StayImage.objects.create(stay=s, image=img)

                    for m_idx, meal in enumerate(meals):
                        images = meal.pop("images", [])
                        meal_fields = {
                            "type": meal.get("type"),
                            "description": meal.get("description"),
                            "restaurant_name": meal.get("restaurant_name"),
                            "location": meal.get("location"),
                            "time": meal.get("time"),
                        }
                        m = Meal.objects.create(day_plan=day_instance, **meal_fields)
                        for img in grouped_images.get((idx, 'meals', m_idx), []):
                            MealImage.objects.create(meal=m, image=img)

                    for a_idx, activity in enumerate(activities):
                        images = activity.pop("images", [])
                        activity_fields = {
                            "name": activity.get("name"),
                            "description": activity.get("description"),
                            "location": activity.get("location"),
                            "time": activity.get("time"),
                        }
                        a = Activity.objects.create(day_plan=day_instance, **activity_fields)
                        for img in grouped_images.get((idx, 'activities', a_idx), []):
                            ActivityImage.objects.create(activity=a, image=img)

            return Response({"message": "Day plans added successfully."}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)









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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    

    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=404)

        # Fetch total bus revenue
        bus_revenue = BusBooking.objects.filter(
            bus__vendor=vendor,
            payment_status__in=["paid", "partial"]
        ).aggregate(total=Sum('total_amount'), count=Count('id'))

        # Fetch total package revenue
        package_revenue = PackageBooking.objects.filter(
            package__vendor=vendor,
            payment_status__in=["paid", "partial"]
        ).aggregate(total=Sum('total_amount'), count=Count('id'))

        # Calculate totals
        total_revenue = float(bus_revenue['total'] or 0) + float(package_revenue['total'] or 0)
        total_bookings = (bus_revenue['count'] or 0) + (package_revenue['count'] or 0)

        return Response({
            "total_revenue": total_revenue,
            "total_bookings": total_bookings
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








class LatestSingleBookingView(APIView):
    def get(self, request):
        latest_bus = BusBooking.objects.order_by('-created_at').first()
        latest_package = PackageBooking.objects.order_by('-created_at').first()

        latest = max(
            filter(None, [latest_bus, latest_package]),
            key=lambda x: x.created_at,
            default=None
        )

        if not latest:
            return Response({"message": "No bookings found."}, status=status.HTTP_204_NO_CONTENT)

        serializer = CombinedBookingSerializer(latest)
        return Response(serializer.data, status=status.HTTP_200_OK)



class VendorBusBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    """API View to get the current vendor's bus bookings"""

    def get(self, request, format=None):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        bookings = BusBooking.objects.filter(bus__vendor=vendor)
        
        total = bookings.filter(
            created_at__year=current_year,
            created_at__month=current_month
        ).aggregate(total=Sum('total_amount'))['total']
        
        monthly_revenue = float(total) if total else 0.0

        serializer = BusBookingDetailSerializer(bookings, many=True)
        
        return Response({
            "bookings": serializer.data,
            "monthly_revenue": monthly_revenue
        }, status=status.HTTP_200_OK)


class BusBookingDetailView(APIView):
    """API View to get full details of a single bus booking"""

    # def get(self, request, booking_id, format=None):
    #     try:
    #         booking = BusBooking.objects.get(id=booking_id)
    #     except BusBooking.DoesNotExist:
    #         return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        
    #     serializer = BusBookingDetailSerializer(booking)
    #     return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request, booking_id, format=None):
        try:
            booking = BusBooking.objects.get(id=booking_id)
        except BusBooking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if booking has travelers
        # if not booking.travelers.exists():
        #     # If no traveler, create a default one
        #     Travelers.objects.create(
        #         bus_booking=booking,
        #         first_name="Default",
        #         last_name="Traveler",
        #         gender="O",  # 'O' for Other
        #         age=18,
        #         email="default@example.com",
        #         mobile="0000000000",
        #         place="Default Place",
        #         city="Default City",
        #     )

        # Serialize and return
        serializer = BusBookingDetailSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)












class BusHistoryFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # def get(self, request):
    #     try:
    #if date_filter == 'last_week':
    #         start_date = (datetime.now() - timedelta(weeks=1)).date()
    #         end_date = datetime.now().date()

    #     elif date_filter == 'last_month':
    #         start_date = (datetime.now() - timedelta(days=30)).date()
    #         end_date = datetime.now().date()

    #     elif date_filter == 'custom' and 'start_date' in request.query_params and 'end_date' in request.query_params:
    #         start_date = request.query_params.get('start_date')
    #         end_date = request.query_params.get('end_date')
    #         try:
    #             start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    #             end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    #         except ValueError:
    #             return Response({"error": "Invalid date format. Use 'YYYY-MM-DD'."}, status=400)

    #     if start_date and end_date:
    #         bookings = BusBooking.objects.filter(
    #             start_date__range=[start_date, end_date],
    #             bus__vendor=vendor   
    #         )
    #     else:
    #         return Response({"error": "Invalid filter."}, status=400)

    #     serializer = BusBookingDetailSerializer(bookings, many=True)
    #     return Response({"bus_bookings": serializer.data})         vendor = Vendor.objects.get(user=request.user)
    #     except Vendor.DoesNotExist:
    #         return Response({"error": "Vendor not found."}, status=404)

    #     date_filter = request.query_params.get('filter', 'today')

    #     start_date = None
    #     end_date = None

    #     if date_filter == 'today':
    #         start_date = datetime.now().date()
    #         end_date = start_date

    #     el

    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        date_filter = request.query_params.get('filter', 'today')

        today = timezone.now().date()

        if date_filter == 'today':
            start_date = today
            end_date = today
        elif date_filter == 'last_week':
            start_date = today - timedelta(days=7)
            end_date = today
        elif date_filter == 'last_month':
            start_date = today - timedelta(days=30)
            end_date = today
        elif date_filter == 'custom' and 'start_date' in request.query_params and 'end_date' in request.query_params:
            try:
                start_date = datetime.strptime(request.query_params.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(request.query_params.get('end_date'), '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use 'YYYY-MM-DD'."}, status=400)
        else:
            return Response({"error": "Invalid filter type."}, status=400)

        bookings = BusBooking.objects.filter(
            start_date__range=[start_date, end_date],
            bus__vendor=vendor
        )

        serializer = BusBookingDetailSerializer(bookings, many=True)

        current_year = timezone.now().year
        current_month = timezone.now().month

        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor)

        # monthly_revenue = all_vendor_bookings.filter(
        #     created_at__year=current_year,
        #     created_at__month=current_month
        # ).aggregate(total=Sum('total_amount'))['total'] or 0


        monthly_revenue = float(
            all_vendor_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )


        return Response({
            "bus_bookings": serializer.data,
            "monthly_revenue": monthly_revenue
        }, status=status.HTTP_200_OK)












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
    





class BusBookingEarningsHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        vendor = request.user.vendor    

        vendor_buses = Bus.objects.filter(vendor=vendor)

        bookings = BusBooking.objects.filter(bus__in=vendor_buses).order_by('-start_date')

        serializer = BusBookingBasicSerializer(bookings, many=True)

        total_revenue = bookings.aggregate(total=Sum('total_amount'))['total'] or 0

        now = timezone.now()
        monthly_bookings = bookings.filter(created_at__year=now.year, created_at__month=now.month)
        monthly_revenue = monthly_bookings.aggregate(total=Sum('total_amount'))['total'] or 0
        monthly_revenue = float(monthly_revenue)




        return Response({"earnings": serializer.data,"total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue,})










class SingleBusBookingDetailView(APIView):
    authentication_classes = [JWTAuthentication]
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










class PackageBookingEarningsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found for the current user."}, status=status.HTTP_404_NOT_FOUND)

            package_bookings = PackageBooking.objects.filter(package__vendor=vendor).order_by('-start_date')
            
            total_revenue = package_bookings.aggregate(total_revenue=Sum('total_amount'))['total_revenue'] or 0.00

            current_month = datetime.now().month
            monthly_revenue = package_bookings.filter(start_date__month=current_month).aggregate(monthly_revenue=Sum('total_amount'))['monthly_revenue'] or 0.00
            
            serializer = PackageBookingEarnigsSerializer(package_bookings, many=True)
            
            return Response({
                "earnings": serializer.data,
                "total_revenue": total_revenue,
                "monthly_revenue": monthly_revenue
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)





class PackageBookingListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]



    def get(self, request, format=None):
        try:
            print('hello')
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=404)

        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        bookings = PackageBooking.objects.filter(package__vendor=vendor)

        monthly_bookings = bookings.filter(
            created_at__year=current_year,
            created_at__month=current_month
        )
        print(monthly_bookings,'bh')

        total = monthly_bookings.aggregate(total=Sum('total_amount'))['total']
        monthly_revenue = float(total) if total else 0.0

        serializer = PackageBookingDetailSerializer(bookings, many=True)

        return Response({
            "bookings": serializer.data,
            "monthly_revenue": monthly_revenue
        }, status=200)




class SinglePackageBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id):
        try:
            package_booking = PackageBooking.objects.get(id=booking_id, user=request.user)
        except PackageBooking.DoesNotExist:
            return Response({"error": "Package booking not found"}, status=404)
        
        serializer = PackageBookingDetailSerializer(package_booking)
        return Response({"package_booking_details": serializer.data})
    



class PackageBookingHistoryFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # def get(self, request):
    #     print('helllo')
    #     user = request.user
        
    #     filter_type = request.query_params.get('filter', 'today')   
        
    #     today = timezone.now().date()
    #     last_week_start = today - timedelta(days=7)
    #     last_month_start = today - timedelta(days=30)

    #     if filter_type == 'today':
    #         start_date = today
    #         end_date = today
    #     elif filter_type == 'last_week':
    #         start_date = last_week_start
    #         end_date = today
    #     elif filter_type == 'last_month':
    #         start_date = last_month_start
    #         end_date = today
    #     elif filter_type == 'custom':
    #         # Get custom date range from params
    #         start_date_str = request.query_params.get('start_date')
    #         end_date_str = request.query_params.get('end_date')
            
    #         if not start_date_str or not end_date_str:
    #             return Response({"error": "Start date and end date are required for custom filter."}, status=400)
            
    #         try:
    #             start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
    #             end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    #         except ValueError:
    #             return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
    #     else:
    #         return Response({"error": "Invalid filter type."}, status=400)

    #     package_bookings = PackageBooking.objects.filter(
    #         user=user,   
    #         start_date__gte=start_date,
    #         start_date__lte=end_date
    #     )
        
    #     serializer = PackageBookingDetailSerializer(package_bookings, many=True)
        
    #     return Response({"package_bookings": serializer.data}, status=200)


 
    def get(self, request):
        user = request.user
        
        filter_type = request.query_params.get('filter', 'today')   
        
        today = timezone.now().date()
        last_week_start = today - timedelta(days=7)
        last_month_start = today - timedelta(days=30)

        if filter_type == 'today':
            start_date = today
            end_date = today
        elif filter_type == 'last_week':
            start_date = last_week_start
            end_date = today
        elif filter_type == 'last_month':
            start_date = last_month_start
            end_date = today
        elif filter_type == 'custom':
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            
            if not start_date_str or not end_date_str:
                return Response({"error": "Start date and end date are required for custom filter."}, status=400)
            
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            return Response({"error": "Invalid filter type."}, status=400)

        package_bookings = PackageBooking.objects.filter(
            user=user,   
            start_date__gte=start_date,
            start_date__lte=end_date
        )
        
        serializer = PackageBookingDetailSerializer(package_bookings, many=True)

        current_year = timezone.now().year
        current_month = timezone.now().month

        all_user_bookings = PackageBooking.objects.filter(user=user)

        # monthly_revenue = all_user_bookings.filter(
        #     created_at__year=current_year,
        #     created_at__month=current_month
        # ).aggregate(total=Sum('total_amount'))['total'] or 0

        monthly_revenue = float(
            all_user_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )


        return Response({
            "package_bookings": serializer.data,
            "monthly_revenue": monthly_revenue
        }, status=200)







class PackageBookingEarningsFilterView(APIView):
    permission_classes = [IsAuthenticated]  
    authentication_classes = [JWTAuthentication] 

  



    def get(self, request):
        vendor = request.user.vendor

        all_bookings = PackageBooking.objects.filter(package__vendor=vendor) 
        package_bookings = all_bookings.order_by('-created_at')

        filter_type = request.query_params.get('filter', None)
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)

        today = now().date()

        if filter_type == 'today':
            start = make_aware(datetime.combine(today, datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            package_bookings = package_bookings.filter(created_at__range=(start, end))

        elif filter_type == 'last_week':
            start = make_aware(datetime.combine(today - timedelta(days=7), datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            package_bookings = package_bookings.filter(created_at__range=(start, end))

        elif filter_type == 'last_month':
            start = make_aware(datetime.combine(today - timedelta(days=30), datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            package_bookings = package_bookings.filter(created_at__range=(start, end))

        elif filter_type == 'custom':
            if start_date and end_date:
                try:
                    start = make_aware(datetime.combine(datetime.strptime(start_date, '%Y-%m-%d'), datetime.min.time()))
                    end = make_aware(datetime.combine(datetime.strptime(end_date, '%Y-%m-%d'), datetime.max.time()))
                    package_bookings = package_bookings.filter(created_at__range=(start, end))
                except ValueError:
                    return Response({"error": "Invalid date format. Please use YYYY-MM-DD."}, status=400)
            else:
                return Response({"error": "Please provide start_date and end_date for custom filter."}, status=400)

        total_revenue = all_bookings.aggregate(total=Sum('total_amount'))['total'] or 0

        first_day = today.replace(day=1)
        start_of_month = make_aware(datetime.combine(first_day, datetime.min.time()))
        monthly_revenue = all_bookings.filter(created_at__gte=start_of_month).aggregate(total=Sum('total_amount'))['total'] or 0

        monthly_revenue = float(monthly_revenue)

        serializer = PackageBookingEarnigsSerializer(package_bookings, many=True)

        return Response({
            "earnings": serializer.data,
            "total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue
        })





class VendorBusyDateCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    

    # def post(self, request):
    #     try:
    #         vendor = Vendor.objects.filter(user=request.user).first()
    #         if not vendor:
    #             return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

    #         serializer = VendorBusyDateSerializer(data=request.data)
    #         if serializer.is_valid():
    #             VendorBusyDate.objects.create(
    #                 vendor=vendor,
    #                 **serializer.validated_data
    #             )
    #             return Response({"message": "Busy date created successfully!"}, status=status.HTTP_201_CREATED)
    #         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



    def post(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = VendorBusyDateSerializer(data=request.data)
            if serializer.is_valid():
                busy_date = serializer.validated_data.get('date')

                if VendorBusyDate.objects.filter(vendor=vendor, date=busy_date).exists():
                    return Response({
                        "message": "Busy date already exists for this day.",
                        "data": {}
                    }, status=status.HTTP_200_OK)


                VendorBusyDate.objects.create(
                    vendor=vendor,
                    **serializer.validated_data
                )
                return Response({"message": "Busy date created successfully!"}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




    def get(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            date_param = request.query_params.get('date', None)

            if date_param:
                try:
                    selected_date = timezone.datetime.strptime(date_param, '%Y-%m-%d').date()
                except ValueError:
                    return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

                busy_date = VendorBusyDate.objects.filter(vendor=vendor, date=selected_date).first()
                if not busy_date:
                    return Response({"error": "No busy date found for the given date."}, status=status.HTTP_404_NOT_FOUND)

                serializer = VendorBusyDateSerializer(busy_date)
                return Response({"busy_date": serializer.data}, status=status.HTTP_200_OK)

            busy_dates = VendorBusyDate.objects.filter(vendor=vendor).order_by('date', 'from_time')
            serializer = VendorBusyDateSerializer(busy_dates, many=True)
            return Response({"busy_dates": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)














    def delete(self, request, pk):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            busy_date = VendorBusyDate.objects.filter(id=pk, vendor=vendor).first()
            if not busy_date:
                return Response({"error": "Busy date not found."}, status=status.HTTP_404_NOT_FOUND)

            busy_date.delete()
            return Response({"message": "Busy date deleted successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

            busy_date = VendorBusyDate.objects.filter(id=pk, vendor=vendor).first()
            if not busy_date:
                return Response({"error": "Busy date not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = VendorBusyDateSerializer(busy_date, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Busy date updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    

from django.utils.timezone import make_aware


class BusBookingEarningsHistoryFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]




   

    
    # def get(self, request):
    #     vendor = request.user.vendor
    #     vendor_buses = Bus.objects.filter(vendor=vendor)
    #     # vendor_buses = Bus.objects.filter(bus__vendor=vendor) 
    #     bookings = BusBooking.objects.filter(bus__in=vendor_buses).order_by('-created_at')

    #     filter_type = request.query_params.get('filter')   
    #     start_date = request.query_params.get('start_date')   
    #     end_date = request.query_params.get('end_date')       

    #     today = timezone.now().date()

    #     if filter_type == 'today':
    #         bookings = bookings.filter(created_at__date=today)

    #     elif filter_type == 'last_week':
    #         last_week_start = today - timedelta(days=7)
    #         bookings = bookings.filter(
    #             created_at__date__gte=last_week_start, created_at__date__lte=today)

    #     elif filter_type == 'last_month':
    #         last_month = today - timedelta(days=30)
    #         bookings = bookings.filter(
    #             created_at__date__gte=last_month, created_at__date__lte=today)

    #     elif filter_type == 'custom':
    #         if start_date and end_date:
    #             try:
    #                 start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
    #                 end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
    #                 bookings = bookings.filter(
    #                     created_at__date__gte=start_date, created_at__date__lte=end_date)
    #             except ValueError:
    #                 return Response({"error": "Invalid date format. Please use YYYY-MM-DD."}, status=400)
    #         else:
    #             return Response({"error": "Please provide start_date and end_date for custom filter."}, status=400)

    #     total_revenue = BusBooking.objects.filter(bus__in=vendor_buses).aggregate(total=Sum('total_amount'))['total'] or 0

    #     first_day_of_month = today.replace(day=1)
    #     monthly_revenue = BusBooking.objects.filter(
    #         bus__in=vendor_buses, created_at__date__gte=first_day_of_month
    #     ).aggregate(total=Sum('total_amount'))['total'] or 0

    #     serializer = BusBookingBasicSerializer(bookings, many=True)

    #     return Response({
    #         "earnings": serializer.data,
    #         "total_revenue": total_revenue,
    #         "monthly_revenue": monthly_revenue,
    #         "sample":"hello"
    #     })


    def get(self, request):
        vendor = request.user.vendor
        vendor_buses = Bus.objects.filter(vendor=vendor)
        bookings = BusBooking.objects.filter(bus__in=vendor_buses).order_by('-created_at')

        filter_type = request.query_params.get('filter')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        today = timezone.now().date()
        now = timezone.now()

        if filter_type == 'today':
            start = make_aware(datetime.combine(today, datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            bookings = bookings.filter(created_at__range=(start, end))

        elif filter_type == 'last_week':
            start = make_aware(datetime.combine(today - timedelta(days=7), datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            bookings = bookings.filter(created_at__range=(start, end))

        elif filter_type == 'last_month':
            start = make_aware(datetime.combine(today - timedelta(days=30), datetime.min.time()))
            end = make_aware(datetime.combine(today, datetime.max.time()))
            bookings = bookings.filter(created_at__range=(start, end))

        elif filter_type == 'custom':
            if start_date and end_date:
                try:
                    start = make_aware(datetime.combine(datetime.strptime(start_date, '%Y-%m-%d').date(), datetime.min.time()))
                    end = make_aware(datetime.combine(datetime.strptime(end_date, '%Y-%m-%d').date(), datetime.max.time()))
                    bookings = bookings.filter(created_at__range=(start, end))
                except ValueError:
                    return Response({"error": "Invalid date format. Please use YYYY-MM-DD."}, status=400)
            else:
                return Response({"error": "Please provide start_date and end_date for custom filter."}, status=400)

        total_revenue = BusBooking.objects.filter(bus__in=vendor_buses).aggregate(
            total=Sum('total_amount'))['total'] or 0

        first_day_of_month = today.replace(day=1)
        month_start = make_aware(datetime.combine(first_day_of_month, datetime.min.time()))
        monthly_revenue = BusBooking.objects.filter(
            bus__in=vendor_buses, created_at__gte=month_start
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        monthly_revenue = float(monthly_revenue)

        serializer = BusBookingBasicSerializer(bookings, many=True)

        return Response({
            "earnings": serializer.data,
            "total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue
        })




# class LatestCanceledBookingView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]

    
#     def get(self, request):
#         vendor = Vendor.objects.filter(user=request.user).first()
#         if not vendor:
#             return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

#         latest_cancelled_bus = BusBooking.objects.filter(
#             bus__vendor=vendor, trip_status='cancelled'
#         ).order_by('-created_at').first()

#         latest_cancelled_package = PackageBooking.objects.filter(
#             package__vendor=vendor, trip_status='cancelled'
#         ).order_by('-created_at').first()

#         latest = max(
#             filter(None, [latest_cancelled_bus, latest_cancelled_package]),
#             key=lambda x: x.created_at,
#             default=None
#         )

#         if not latest:
#             return Response({"message": "No cancelled bookings found."}, status=status.HTTP_204_NO_CONTENT)

#         serializer = CombinedBookingSerializer(latest)
#         return Response(serializer.data, status=status.HTTP_200_OK)


class LatestCanceledBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    
    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        latest_cancelled_bus = BusBooking.objects.filter(
            bus__vendor=vendor, trip_status='cancelled'
        ).order_by('-created_at').first()

        latest_cancelled_package = PackageBooking.objects.filter(
            package__vendor=vendor, trip_status='cancelled'
        ).order_by('-created_at').first()

        latest = max(
            filter(None, [latest_cancelled_bus, latest_cancelled_package]),
            key=lambda x: x.created_at,
            default=None
        )

        if not latest:
#             return Response({"message": "No cancelled bookings found."}, status=status.HTTP_204_NO_CONTENT)

#         serializer = CombinedBookingSerializer(latest)
#         return Response(serializer.data, status=status.HTTP_200_OK)

            return Response({
                "message": "No cancelled bookings found.",
                "data": {}
            }, status=status.HTTP_200_OK)

        serializer = CombinedBookingSerializer(latest)
        return Response({
            "message": "Latest cancelled booking retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)







class CanceledBusBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

   


    # def get(self, request, booking_id=None):
    #     vendor = request.user.vendor

    #     now = timezone.now()
    #     current_year = now.year
    #     current_month = now.month

    #     all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor)

       
    #     monthly_revenue = float(
    #         all_vendor_bookings.filter(
    #             created_at__year=current_year,
    #             created_at__month=current_month
    #         ).aggregate(total=Sum('total_amount'))['total'] or 0
    #     )


    #     if booking_id:
    #         try:
    #             canceled_booking = BusBooking.objects.get(
    #                 id=booking_id, 
    #                 payment_status='cancelled',
    #                 bus__vendor=vendor
    #             )
    #             serializer = BusBookingDetailSerializer(canceled_booking)
    #             return Response({
    #                 "canceled_bus_booking": serializer.data,
    #                 "monthly_revenue": monthly_revenue
    #             }, status=status.HTTP_200_OK)
    #         except BusBooking.DoesNotExist:
    #             return Response({
    #                 "error": "Canceled bus booking not found",
    #                 "monthly_revenue": monthly_revenue
    #             }, status=status.HTTP_404_NOT_FOUND)
    #     else:
    #         canceled_bookings = BusBooking.objects.filter(
    #             payment_status='cancelled',
    #             bus__vendor=vendor
    #         ).order_by('-created_at')

    #         if canceled_bookings.exists():
    #             serializer = BusBookingBasicSerializer(canceled_bookings, many=True)
    #             return Response({
    #                 "canceled_bus_bookings": serializer.data,
    #                 "monthly_revenue": monthly_revenue
    #             }, status=status.HTTP_200_OK)
    #         else:
    #             return Response({
    #                 "message": "No canceled bus bookings found for this vendor.",
    #                 "monthly_revenue": monthly_revenue
    #             }, status=status.HTTP_404_NOT_FOUND)


    def get(self, request, booking_id=None):
        vendor = request.user.vendor

        now = timezone.now()
        current_year = now.year
        current_month = now.month

        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor)

        monthly_revenue = float(
            all_vendor_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )

        cancel_filter = Q(payment_status='cancelled') | Q(trip_status='cancelled') | Q(booking_status='cancelled')

        if booking_id:
            try:
                canceled_booking = BusBooking.objects.get(
                    Q(id=booking_id) & Q(bus__vendor=vendor) & cancel_filter
                )
                serializer = BusBookingDetailSerializer222(canceled_booking)
                return Response({
                    "canceled_bus_booking": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            except BusBooking.DoesNotExist:
                return Response({
                    "error": "Canceled bus booking not found",
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            canceled_bookings = BusBooking.objects.filter(
                Q(bus__vendor=vendor) & cancel_filter
            ).order_by('-created_at')

            if canceled_bookings.exists():
                serializer = BusBookingDetailSerializer222(canceled_bookings, many=True)
                return Response({
                    "canceled_bus_bookings": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            else:
                # return Response({
                #     "message": "No canceled bus bookings found for this vendor.",
                #     "monthly_revenue": monthly_revenue
                # }, status=status.HTTP_404_NOT_FOUND)
                return Response({
            "canceled_bus_bookings": [],
            "monthly_revenue": monthly_revenue
        }, status=status.HTTP_200_OK)









class CanceledBusBookingFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id=None):
        vendor = request.user.vendor
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        # All vendor bookings
        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor)

        # Monthly revenue calculation
        monthly_revenue = float(
            all_vendor_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )

        # Common cancellation logic
        cancel_filter = Q(payment_status='cancelled') | Q(trip_status='cancelled') | Q(booking_status='cancelled')

        # If booking ID is provided (single booking fetch)
        if booking_id:
            try:
                canceled_booking = BusBooking.objects.get(
                    Q(id=booking_id) & Q(bus__vendor=vendor) & cancel_filter
                )
                serializer = BusBookingDetailSerializer222(canceled_booking)
                return Response({
                    "canceled_bus_booking": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            except BusBooking.DoesNotExist:
                return Response({
                    "error": "Canceled bus booking not found",
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_404_NOT_FOUND)

        # Multiple bookings view with filters
        canceled_bookings = BusBooking.objects.filter(
            Q(bus__vendor=vendor) & cancel_filter
        )

        # Filter by query params
        filter_param = request.query_params.get('filter')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if filter_param == "today":
            canceled_bookings = canceled_bookings.filter(
                created_at__date=now.date()
            )
        elif filter_param == "last_week":
            last_week = now - timedelta(days=7)
            canceled_bookings = canceled_bookings.filter(
                created_at__date__gte=last_week.date(),
                created_at__date__lte=now.date()
            )
        elif start_date and end_date:
            try:
                canceled_bookings = canceled_bookings.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
            except ValueError:
                return Response({
                    "error": "Invalid date format. Use YYYY-MM-DD."
                }, status=status.HTTP_400_BAD_REQUEST)

        # Serialize and return
        if canceled_bookings.exists():
            serializer = BusBookingDetailSerializer222(canceled_bookings.order_by('-created_at'), many=True)
            return Response({
                "canceled_bus_bookings": serializer.data,
                "monthly_revenue": monthly_revenue
            }, status=status.HTTP_200_OK)
        else:
            # return Response({
            #     "message": "No canceled bus bookings found for this vendor.",
            #     "monthly_revenue": monthly_revenue
            # }, status=status.HTTP_404_NOT_FOUND)

            return Response({
            "canceled_bus_bookings": [],
            "monthly_revenue": monthly_revenue
        }, status=status.HTTP_200_OK)












class CanceledPackageBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
   

    def get(self, request, booking_id=None):
        vendor = request.user.vendor
        print('hai')

        now = timezone.now()
        current_year = now.year
        current_month = now.month

        all_vendor_package_bookings = PackageBooking.objects.filter(package__vendor=vendor)

        monthly_revenue = float(
            all_vendor_package_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )

        cancel_conditions = Q(payment_status="cancelled") | Q(booking_status="declined") | Q(trip_status="cancelled")

        if booking_id:
            try:
                canceled_package_booking = PackageBooking.objects.get(
                    Q(id=booking_id) & cancel_conditions & Q(package__vendor=vendor)
                )
                serializer = PackageBookingDetailSerializer222(canceled_package_booking)
                return Response({
                    "canceled_package_booking": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            except PackageBooking.DoesNotExist:
                return Response({
                    "error": "Canceled package booking not found",
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            canceled_package_bookings = PackageBooking.objects.filter(
                cancel_conditions,
                package__vendor=vendor
            ).order_by('-created_at')

            if canceled_package_bookings.exists():
                serializer = PackageBookingDetailSerializer222(canceled_package_bookings, many=True)
                return Response({
                    "canceled_package_bookings": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            else:
                # return Response({
                #     "message": "No canceled package bookings found for this vendor.",
                #     "monthly_revenue": monthly_revenue
                # }, status=status.HTTP_404_NOT_FOUND)

                return Response({
                "canceled_bus_bookings": [],
                "monthly_revenue": monthly_revenue
            }, status=status.HTTP_200_OK)








class CanceledPackageBookingFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id=None):
        vendor = request.user.vendor
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        all_vendor_package_bookings = PackageBooking.objects.filter(package__vendor=vendor)

        monthly_revenue = float(
            all_vendor_package_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )

        cancel_conditions = Q(payment_status="cancelled") | Q(booking_status="declined") | Q(trip_status="cancelled")

        # === Filter by Booking ID ===
        if booking_id:
            try:
                canceled_booking = PackageBooking.objects.get(
                    Q(id=booking_id) & cancel_conditions & Q(package__vendor=vendor)
                )
                serializer = PackageBookingDetailSerializer222(canceled_booking)
                return Response({
                    "canceled_package_booking": serializer.data,
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_200_OK)
            except PackageBooking.DoesNotExist:
                return Response({
                    "error": "Canceled package booking not found",
                    "monthly_revenue": monthly_revenue
                }, status=status.HTTP_404_NOT_FOUND)

        # === Time-based Filters ===
        filter_type = request.query_params.get('filter')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        queryset = PackageBooking.objects.filter(cancel_conditions, package__vendor=vendor)

        if filter_type == "today":
            queryset = queryset.filter(created_at__date=now.date())

        elif filter_type == "last_week":
            last_week = now - timedelta(days=7)
            queryset = queryset.filter(created_at__date__gte=last_week.date())

        elif filter_type == "custom":
            if not start_date or not end_date:
                raise ValidationError("Both start_date and end_date must be provided for custom filter.")
            try:
                queryset = queryset.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
            except Exception:
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

        queryset = queryset.order_by('-created_at')

        if queryset.exists():
            serializer = PackageBookingDetailSerializer222(queryset, many=True)
            return Response({
                "canceled_package_bookings": serializer.data,
                "monthly_revenue": monthly_revenue
            }, status=status.HTTP_200_OK)
        else:
            # return Response({
            #     "message": "No canceled package bookings found.",
            #     "monthly_revenue": monthly_revenue
            # }, status=status.HTTP_404_NOT_FOUND)
            return Response({
            "canceled_bus_bookings": [],
            "monthly_revenue": monthly_revenue
        }, status=status.HTTP_200_OK)

            



















class AcceptedBusBookingListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = request.user.vendor   
            
            accepted_bus_bookings = BusBooking.objects.filter(
                booking_status='accepted',   
                bus__vendor=vendor
            ).order_by('-created_at')

            if accepted_bus_bookings.exists():
                serializer = BusBookingBasicSerializer(accepted_bus_bookings, many=True)
                return Response({"accepted_bus_bookings": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No accepted bus bookings found for this vendor."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




class DeclinedBusBookingListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = request.user.vendor 
            
            declined_bus_bookings = BusBooking.objects.filter(
                booking_status='declined',    
                bus__vendor=vendor
            ).order_by('-created_at')

            if declined_bus_bookings.exists():
                serializer = BusBookingBasicSerializer(declined_bus_bookings, many=True)
                return Response({"declined_bus_bookings": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No declined bus bookings found for this vendor."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






class AcceptBusBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, booking_id):
        try:
            vendor = request.user.vendor
            bus_booking = BusBooking.objects.get(id=booking_id, bus__vendor=vendor)

            if bus_booking.booking_status != 'pending':
                return Response({"error": "Booking is already accepted or declined."}, status=status.HTTP_400_BAD_REQUEST)

            driver_serializer = BusDriverDetailSerializer(data=request.data)
            if driver_serializer.is_valid():
                driver_serializer.save(bus_booking=bus_booking)

                bus_booking.booking_status = 'accepted'
                bus_booking.save()

                return Response({
                    "message": "Bus booking accepted and driver details added successfully.",
                    "driver_details": driver_serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response(driver_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except BusBooking.DoesNotExist:
            return Response({"error": "Bus booking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






class AcceptedBusBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id):
        try:
            vendor = request.user.vendor   
            bus_booking = BusBooking.objects.filter(
                id=booking_id, 
                booking_status='accepted',  
                bus__vendor=vendor   
            ).first()

            if bus_booking:
                serializer = AcceptedBusBookingSerializer(bus_booking)
                return Response({"bus_booking_details": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No accepted bus booking found with this ID for the current vendor."}, 
                                 status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class AcceptPackageBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, booking_id):
        print('is working',booking_id)
        try:
            vendor = request.user.vendor   
            package_booking = PackageBooking.objects.filter(
                id=booking_id, 
                booking_status='pending',   
                package__vendor=vendor   
            ).first()

            if package_booking:
                driver_name = request.data.get('name')
                driver_place = request.data.get('place')
                driver_phone_number = request.data.get('phone_number')
                driver_image = request.FILES.get('driver_image')  
                license_image = request.FILES.get('license_image')  
                experience = request.data.get('experience')
                age = request.data.get('age')
                
                print('1')
                driver_details = PackageDriverDetail.objects.create(
                    package_booking=package_booking,
                    name=driver_name,
                    place=driver_place,
                    phone_number=driver_phone_number,
                    driver_image=driver_image,
                    license_image=license_image,
                    experience=experience,
                    age=age
                )

                print('2')

                package_booking.booking_status = 'accepted'
                package_booking.save()

                return Response({"message": "Package booking accepted and driver details created."}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No pending package booking found with this ID for the current vendor."}, 
                                 status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)





class AcceptedPackageBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id):
        try:
            vendor = request.user.vendor   
            package_booking = PackageBooking.objects.filter(
                id=booking_id, 
                booking_status='accepted',   
                package__vendor=vendor   
            ).first()

            if package_booking:
                serializer = AcceptedPackageBookingSerializer(package_booking)
                return Response({"package_booking_details": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No accepted package booking found with this ID for the current vendor."}, 
                                 status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        





# views.py

class AcceptedPackageBookingListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = request.user.vendor   
            accepted_bookings = PackageBooking.objects.filter(
                booking_status='accepted',   
                package__vendor=vendor   
            )
            
            if accepted_bookings.exists():
                serializer = PackageBookingListSerializer(accepted_bookings, many=True)
                return Response({"accepted_package_bookings": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No accepted package bookings found for the current vendor."}, 
                                 status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




class DeclinePackageBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = request.user.vendor

            declined_bookings = PackageBooking.objects.filter(
                booking_status='declined',   
                package__vendor=vendor   
            )

            serializer = PackageBookingListSerializer(declined_bookings, many=True)

            return Response({"declined_bookings": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)







class DeclineBusBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, booking_id):
        try:
            vendor = request.user.vendor
            bus_booking = BusBooking.objects.get(id=booking_id, bus__vendor=vendor)

            if bus_booking.booking_status != 'pending':
                return Response({"error": "Booking is already accepted or declined."}, status=status.HTTP_400_BAD_REQUEST)

            cancelation_reason = request.data.get('cancelation_reason')

            if not cancelation_reason:
                return Response({"error": "Cancellation reason is required."}, status=status.HTTP_400_BAD_REQUEST)

            bus_booking.booking_status = 'declined'
            bus_booking.cancelation_reason = cancelation_reason
            bus_booking.save()

            return Response({
                "message": "Bus booking has been declined successfully.",
                "cancelation_reason": cancelation_reason
            }, status=status.HTTP_200_OK)

        except BusBooking.DoesNotExist:
            return Response({"error": "Bus booking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)








class DeclinePackageBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, booking_id):
        try:
            vendor = request.user.vendor
            package_booking = PackageBooking.objects.get(id=booking_id, package__vendor=vendor)

            if package_booking.booking_status != 'pending':
                return Response({"error": "Booking is already accepted or declined."}, status=status.HTTP_400_BAD_REQUEST)

            reason = request.data.get('cancelation_reason', '').strip()
            if not reason:
                return Response({"error": "Cancelation reason is required."}, status=status.HTTP_400_BAD_REQUEST)

            package_booking.booking_status = 'declined'
            package_booking.cancelation_reason = reason
            package_booking.save()

            return Response({
                "message": "Package booking declined successfully.",
                "cancelation_reason": reason
            }, status=status.HTTP_200_OK)

        except PackageBooking.DoesNotExist:
            return Response({"error": "Package booking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






class BusBookingRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            vendor = request.user.vendor

            vendor_buses = Bus.objects.filter(vendor=vendor)

            pending_bookings = BusBooking.objects.filter(
                bus__in=vendor_buses,
                booking_status='pending'
            ).order_by('-created_at')

            confirmed_bookings = BusBooking.objects.filter(
                bus__in=vendor_buses,
                booking_status='accepted'
            ).order_by('-created_at')

            pending_serializer = BusBookingRequestSerializer(pending_bookings, many=True)
            confirmed_serializer = BusBookingRequestSerializer(confirmed_bookings, many=True)

            return Response({
                "pending_requests": pending_serializer.data,
                "confirmed_bookings": confirmed_serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)





class PackageBookingRequestView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            print('hello')
            vendor = request.user.vendor

            pending_bookings = PackageBooking.objects.filter(
                package__vendor=vendor,
                booking_status='pending'
            ).order_by('-created_at')

            accepted_bookings = PackageBooking.objects.filter(
                package__vendor=vendor,
                booking_status='accepted'
            ).order_by('-created_at')

            pending_serializer = PackageBookingREQUESTSerializer(pending_bookings, many=True)
            accepted_serializer = PackageBookingREQUESTSerializer(accepted_bookings, many=True)

            return Response({
                "pending_requests": pending_serializer.data,
                "confirmed_bookings": accepted_serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)








class VendorLatestSingleBookingHistoryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # def get(self, request):
    #     vendor = Vendor.objects.filter(user=request.user).first()
    #     if not vendor:
    #         return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

    #     latest_bus = BusBooking.objects.filter(bus__vendor=vendor).order_by('-created_at').first()
    #     latest_package = PackageBooking.objects.filter(package__vendor=vendor).order_by('-created_at').first()

    #     latest = max(
    #         filter(None, [latest_bus, latest_package]),
    #         key=lambda x: x.created_at,
    #         default=None
    #     )

    #     if not latest:
    #         return Response({"message": "No bookings found."}, status=status.HTTP_204_NO_CONTENT)

    #     serializer = CombinedBookingSerializer(latest)
    #     return Response(serializer.data, status=status.HTTP_200_OK)

# class VendorLatestSingleBookingHistoryView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

  

#     def get(self, request):
#         vendor = Vendor.objects.filter(user=request.user).first()
#         if not vendor:
#             return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

#         latest_completed_bus = BusBooking.objects.filter(
#             bus__vendor=vendor, trip_status='completed'
#         ).order_by('-created_at').first()

#         latest_completed_package = PackageBooking.objects.filter(
#             package__vendor=vendor, trip_status='completed'
#         ).order_by('-created_at').first()

#         latest = max(
#             filter(None, [latest_completed_bus, latest_completed_package]),
#             key=lambda x: x.created_at,
#             default=None
#         )

#         if not latest:
#             return Response({"message": "No completed bookings found."}, status=status.HTTP_204_NO_CONTENT)

#         serializer = CombinedBookingSerializer(latest)
#         return Response(serializer.data, status=status.HTTP_200_OK)
    


class VendorLatestSingleBookingHistoryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        latest_completed_bus = BusBooking.objects.filter(
            bus__vendor=vendor, trip_status='completed'
        ).order_by('-created_at').first()

        latest_completed_package = PackageBooking.objects.filter(
            package__vendor=vendor, trip_status='completed'
        ).order_by('-created_at').first()

        latest = max(
            filter(None, [latest_completed_bus, latest_completed_package]),
            key=lambda x: x.created_at,
            default=None
        )

        if not latest:
#             return Response({"message": "No completed bookings found."}, status=status.HTTP_204_NO_CONTENT)

#         serializer = CombinedBookingSerializer(latest)
#         return Response(serializer.data, status=status.HTTP_200_OK)
    

            return Response({
                "message": "No completed bookings found.",
                "data": {}
            }, status=status.HTTP_200_OK)

        serializer = CombinedBookingSerializer(latest)
        return Response({
            "message": "Latest completed booking retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)





class VendorLatestCancelledBookingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        latest_cancelled_bus = BusBooking.objects.filter(
            bus__vendor=vendor, trip_status='cancelled'
        ).order_by('-created_at').first()

        latest_cancelled_package = PackageBooking.objects.filter(
            package__vendor=vendor, trip_status='cancelled'
        ).order_by('-created_at').first()

        latest = max(
            filter(None, [latest_cancelled_bus, latest_cancelled_package]),
            key=lambda x: x.created_at,
            default=None
        )

        if not latest:
            return Response({"message": "No cancelled bookings found."}, status=status.HTTP_204_NO_CONTENT)

        serializer = CombinedBookingSerializer(latest)
        return Response(serializer.data, status=status.HTTP_200_OK)





# BOOKED VIEW DETAILS  BUS AND PACKAGE
class UnifiedBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

  
    # def get(self, request, booking_id):
    #     try:
    #         vendor = request.user.vendor  

    #         bus_booking = BusBooking.objects.filter(
    #             id=booking_id,
    #             bus__vendor=vendor  
    #         ).first()

    #         if bus_booking:
    #             data = {
    #                 "booking_type": "bus",
    #                 "from_location": bus_booking.from_location,
    #                 "to_location": bus_booking.to_location,
    #                 "start_date": bus_booking.start_date,
    #                 "way": bus_booking.way if hasattr(bus_booking, 'way') else "one-way",   
    #                 "total_travelers": bus_booking.total_travelers,
    #                 "total_amount": package_booking.total_amount,
    #                 "advance_amount": package_booking.advance_amount,
    #                 "balance_amount": package_booking.balance_amount,
    #                 "male": bus_booking.male,
    #                 "female": bus_booking.female,
    #                 "children": bus_booking.children,
    #                 "traveler": TravelerSerializer(bus_booking.travelers.first()).data if bus_booking.travelers.exists() else None
    #             }
    #             return Response(data, status=status.HTTP_200_OK)

    #         package_booking = PackageBooking.objects.filter(
    #             id=booking_id,
    #             package__vendor=vendor   
    #         ).first()

    #         if package_booking:
    #             data = {
    #                 "booking_type": "package",
    #                 "from_location": package_booking.from_location,
    #                 "to_location": package_booking.to_location,
    #                 "start_date": package_booking.start_date,
    #                 "way": package_booking.way if hasattr(package_booking, 'way') else "round-trip",   
    #                 "total_travelers": package_booking.total_travelers,
    #                 "male": package_booking.male,
    #                 "total_amount": package_booking.total_amount,
    #                 "advance_amount": package_booking.advance_amount,
    #                 "balance_amount": package_booking.balance_amount,
    #                 "female": package_booking.female,
    #                 "children": package_booking.children,
    #                 "traveler": TravelerSerializer(package_booking.travelers.first()).data if package_booking.travelers.exists() else None
    #             }
    #             return Response(data, status=status.HTTP_200_OK)

    #         return Response({"message": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




    def get(self, request, booking_id):
        try:
            vendor = request.user.vendor  

            bus_booking = BusBooking.objects.filter(
                id=booking_id,
                bus__vendor=vendor
            ).first()

            if bus_booking:
                driver_detail = None
                if hasattr(bus_booking, 'driver_detail'):
                    driver_detail = BusDriverDetailSerializer(bus_booking.driver_detail).data

                data = {
                    "booking_type": "bus",
                    "from_location": bus_booking.from_location,
                    "to_location": bus_booking.to_location,
                    "start_date": bus_booking.start_date,
                    "way": getattr(bus_booking, 'way', "one-way"),
                    "total_travelers": bus_booking.total_travelers,
                    "total_amount": bus_booking.total_amount,
                    "advance_amount": bus_booking.advance_amount,
                    "balance_amount": bus_booking.balance_amount,
                    "male": bus_booking.male,
                    "female": bus_booking.female,
                    "children": bus_booking.children,
                    "traveler": TravelerSerializer(bus_booking.travelers.first()).data if bus_booking.travelers.exists() else None,
                    "driver_detail": driver_detail
                }
                return Response(data, status=status.HTTP_200_OK)

            package_booking = PackageBooking.objects.filter(
                id=booking_id,
                package__vendor=vendor
            ).first()

            if package_booking:
                driver_detail = None
                if hasattr(package_booking, 'driver_detail'):
                    driver_detail = PackageDriverDetailSerializer(package_booking.driver_detail).data

                data = {
                    "booking_type": "package",
                    "from_location": package_booking.from_location,
                    "to_location": package_booking.to_location,
                    "start_date": package_booking.start_date,
                    "way": getattr(package_booking, 'way', "round-trip"),
                    "total_travelers": package_booking.total_travelers,
                    "male": package_booking.male,
                    "female": package_booking.female,
                    "children": package_booking.children,
                    "total_amount": package_booking.total_amount,
                    "advance_amount": package_booking.advance_amount,
                    "balance_amount": package_booking.balance_amount,
                    "traveler": TravelerSerializer(package_booking.travelers.first()).data if package_booking.travelers.exists() else None,
                    "driver_detail": driver_detail
                }
                return Response(data, status=status.HTTP_200_OK)

            return Response({"message": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)








class PreAcceptPackageBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id):
        try:
            vendor = request.user.vendor

            # Try BusBooking first
            bus_booking = BusBooking.objects.filter(
                id=booking_id,
                bus__vendor=vendor,
                booking_status='pending'  # pending = not accepted yet
            ).first()

            if bus_booking:
                data = {
                    "booking_type": "bus",
                    "from_location": bus_booking.from_location,
                    "to_location": bus_booking.to_location,
                    "start_date": bus_booking.start_date,
                    "total_travelers": bus_booking.total_travelers,
                    "male": bus_booking.male,
                    "female": bus_booking.female,
                    "children": bus_booking.children,
                    "travelers": TravelerSerializer(bus_booking.travelers.all(), many=True).data
                }
                return Response(data, status=status.HTTP_200_OK)

            # Then try PackageBooking
            package_booking = PackageBooking.objects.filter(
                id=booking_id,
                package__vendor=vendor,
                booking_status='pending'
            ).first()

            if package_booking:
                data = {
                    "booking_type": "package",
                    "from_location": package_booking.from_location,
                    "to_location": package_booking.to_location,
                    "start_date": package_booking.start_date,
                    "total_travelers": package_booking.total_travelers,
                    "male": package_booking.male,
                    "female": package_booking.female,
                    "children": package_booking.children,
                    "travelers": TravelerSerializer(package_booking.travelers.all(), many=True).data
                }
                return Response(data, status=status.HTTP_200_OK)

            return Response({"message": "No pending booking found for this vendor with given ID."},
                            status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



# LATEST BOOKINV DETAILS VIEW
class BookingDetailByIdView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, booking_id):
        try:
            vendor = request.user.vendor

            # Try to find a matching BusBooking
            bus_booking = BusBooking.objects.filter(id=booking_id, bus__vendor=vendor).first()
            if bus_booking:
                traveler = bus_booking.travelers.first() if bus_booking.travelers.exists() else None
                traveler_data = {
                    "name": f"{traveler.first_name} {traveler.last_name}" if traveler else None,
                    "dob": traveler.dob if traveler else None,
                    "email": traveler.email if traveler else None,
                    "contact": traveler.mobile if traveler else None,
                    "city": traveler.city if traveler else None,
                    "id_proof": traveler.id_proof.url if traveler and traveler.id_proof else None,
                }

                data = {
                    "booking_type": "bus",
                    "from_location": bus_booking.from_location,
                    "to_location": bus_booking.to_location,
                    "start_date": bus_booking.start_date,
                    "way": getattr(bus_booking, 'way', 'one-way'),
                    "total_travelers": bus_booking.total_travelers,
                    "male": bus_booking.male,
                    "female": bus_booking.female,
                    "children": bus_booking.children,

                    "passenger": traveler_data,

                    "total_fare": bus_booking.total_amount,
                    "paid_amount": bus_booking.advance_amount,
                    "balance_amount": bus_booking.balance_amount,
                }
                return Response(data, status=status.HTTP_200_OK)

            # Try to find a matching PackageBooking
            package_booking = PackageBooking.objects.filter(id=booking_id, package__vendor=vendor).first()
            if package_booking:
                traveler = package_booking.travelers.first() if package_booking.travelers.exists() else None
                traveler_data = {
                    "name": f"{traveler.first_name} {traveler.last_name}" if traveler else None,
                    "dob": traveler.dob if traveler else None,
                    "email": traveler.email if traveler else None,
                    "contact": traveler.mobile if traveler else None,
                    "city": traveler.city if traveler else None,
                    "id_proof": traveler.id_proof.url if traveler and traveler.id_proof else None,
                }

                data = {
                    "booking_type": "package",
                    "from_location": package_booking.from_location,
                    "to_location": package_booking.to_location,
                    "start_date": package_booking.start_date,
                    "way": getattr(package_booking, 'way', 'round-trip'),
                    "total_travelers": package_booking.total_travelers,
                    "male": package_booking.male,
                    "female": package_booking.female,
                    "children": package_booking.children,

                    "passenger": traveler_data,

                    "total_fare": package_booking.total_amount,
                    "paid_amount": package_booking.advance_amount,
                    "balance_amount": package_booking.balance_amount,
                }
                return Response(data, status=status.HTTP_200_OK)

            return Response({"message": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)







