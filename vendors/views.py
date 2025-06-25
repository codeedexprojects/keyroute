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
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
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
# from datetime import datetime, timedelta
from bookings.models import *
from django.db.models import Sum, Count, F
from django.utils.timezone import now
from .serializers import PackageBasicSerializer
from admin_panel.models import *
from calendar import monthrange
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
from admin_panel.utils import send_otp, verify_otp, is_valid_email
from bookings.serializers import BusBookingStopSerializer


# Create your views here.

class VendorSignupAPIView(APIView):
    def post(self, request):
        print(request.data, 'data')
        
        # First validate the data without creating user
        serializer = VendorSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get mobile and email from validated data
        mobile = request.data.get('mobile')
        email = request.data.get('email_address')
        
        # Determine where to send OTP
        otp_sent_to = None
        
        if mobile and email:
            # Both provided, send to mobile (priority)
            otp_sent_to = "mobile"
            identifier = mobile
        elif mobile:
            # Only mobile provided
            otp_sent_to = "mobile"
            identifier = mobile
        elif email:
            # Only email provided
            otp_sent_to = "email"
            identifier = email
        else:
            return Response(
                {"errors": "Either mobile number or email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete any existing OTP for this identifier
        SignupOTP.objects.filter(identifier=identifier).delete()
        
        # Create new OTP record
        signup_otp = SignupOTP.objects.create(
            identifier=identifier,
            signup_data=request.data,
            otp_type=otp_sent_to
        )
        
        # Generate OTP
        otp_code = signup_otp.generate_otp()
        
        # Send OTP
        if otp_sent_to == "mobile":
            try:
                otp_response = send_otp(identifier)
                if otp_response.get("Status") == "Success":
                    return Response({
                        "message": "OTP sent successfully!",
                        "otp_sent_to": "mobile",
                        "identifier": identifier
                    }, status=status.HTTP_200_OK)
                else:
                    signup_otp.delete()  # Clean up if failed
                    return Response(
                        {"errors": "Failed to send OTP via SMS."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                signup_otp.delete()  # Clean up if failed
                return Response(
                    {"errors": f"Failed to send OTP: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        else:  # email
            try:
                subject = "Your OTP for Vendor Registration"
                message = f"Your OTP code is {otp_code}. It is valid for 5 minutes."
                from_email = "praveen.codeedex@gmail.com"
                
                from django.core.mail import send_mail
                send_mail(subject, message, from_email, [identifier])
                
                return Response({
                    "message": "OTP sent successfully!",
                    "otp_sent_to": "email",
                    "identifier": identifier
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                signup_otp.delete()  # Clean up if failed
                return Response(
                    {"errors": f"Failed to send OTP via email: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
class VerifySignupOtpAPIView(APIView):
    def post(self, request):
        identifier = request.data.get('identifier')
        otp = request.data.get('otp')
        
        if not identifier or not otp:
            return Response(
                {"errors": "Identifier and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the OTP record
            signup_otp = SignupOTP.objects.get(
                identifier=identifier,
                is_verified=False
            )
        except SignupOTP.DoesNotExist:
            return Response(
                {"errors": "Invalid request. Please start registration again."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if OTP is expired
        if signup_otp.is_expired():
            signup_otp.delete()
            return Response(
                {"errors": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP based on type
        otp_valid = False
        
        if signup_otp.otp_type == "mobile":
            try:
                verification_response = verify_otp(identifier, otp)
                if verification_response.get("Status") == "Success":
                    otp_valid = True
            except Exception as e:
                return Response(
                    {"errors": f"OTP verification failed: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif signup_otp.otp_type == "email":
            if signup_otp.otp_code == otp:
                otp_valid = True
        
        if not otp_valid:
            return Response(
                {"errors": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # OTP verified successfully, now create the vendor
        serializer = VendorSerializer(data=signup_otp.signup_data)
        if serializer.is_valid():
            vendor = serializer.save()
            
            # Mark OTP as verified and delete
            signup_otp.is_verified = True
            signup_otp.save()
            signup_otp.delete()  # Clean up
            
            return Response(
                {
                    "message": "Vendor registered successfully!",
                    "data": VendorSerializer(vendor).data
                },
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

    
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
        travels_name = ""
        try:
            vendor_name = user.vendor.full_name
            travels_name = user.vendor.travels_name
        except Vendor.DoesNotExist:
            pass
            
        return Response({
            "message": "Login successful!",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "vendor_name": vendor_name,
            "travels_name": travels_name
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
        identifier = request.data.get('email_phone')
        if not identifier:
            return Response({"error": "Email or phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        if is_valid_email(identifier):  
            try:
                vendor = Vendor.objects.get(email_address=identifier)
                otp_instance, _ = OTP.objects.get_or_create(user=vendor.user)
                otp = otp_instance.generate_otp()

                subject = "Your OTP for Password Reset"
                message = f"Your OTP code is {otp}. It is valid for 5 minutes."
                from_email = "praveen.codeedex@gmail.com"
                send_mail(subject, message, from_email, [identifier])

                return Response({"message": "OTP sent to email!"}, status=status.HTTP_200_OK)

            except Vendor.DoesNotExist:
                return Response({"error": "No vendor found with this email."}, status=status.HTTP_404_NOT_FOUND)

        else:
            try:
                vendor = User.objects.get(mobile=identifier)
                
                if vendor.role.lower() == 'vendor':
                    otp_response = send_otp(identifier)

                    if otp_response.get("Status") == "Success":
                        return Response({"message": "OTP sent to phone!"}, status=status.HTTP_200_OK)
                    else:
                        return Response({"error": "Failed to send OTP via SMS."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": "User is not a vendor."}, status=status.HTTP_403_FORBIDDEN)

            except User.DoesNotExist:
                return Response({"error": "No vendor found with this phone number."}, status=status.HTTP_404_NOT_FOUND)


# OTP VERIFCATION
class VerifyOtpAPIView(APIView):
    def post(self, request):
        identifier = request.data.get('email_phone')
        otp = request.data.get('otp')

        if not identifier or not otp:
            return Response({"error": "Email/Phone and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        if is_valid_email(identifier):  # Verify Email OTP
            try:
                vendor = Vendor.objects.get(email_address=identifier)
                otp_instance = OTP.objects.get(user=vendor.user)

                if otp_instance.otp_code != otp:
                    return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

                if not otp_instance.is_valid():
                    return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

                return Response({"message": "OTP verified successfully!"}, status=status.HTTP_200_OK)

            except (Vendor.DoesNotExist, OTP.DoesNotExist):
                return Response({"error": "Invalid email or OTP."}, status=status.HTTP_404_NOT_FOUND)

        else:  # Verify Phone OTP using 2Factor API
            try:
                user = User.objects.get(mobile=identifier)

                if user.role.lower() == 'vendor':
                    verification_response = verify_otp(identifier, otp)

                    if verification_response.get("Status") == "Success":
                        return Response({"message": "OTP verified successfully!"}, status=status.HTTP_200_OK)
                    else:
                        return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": "User is not a vendor."}, status=status.HTTP_403_FORBIDDEN)

            except User.DoesNotExist:
                return Response({"error": "Invalid phone number or OTP."}, status=status.HTTP_404_NOT_FOUND)


# RESET PASSWORD
class ResetPasswordAPIView(APIView):
    def post(self, request):

        email_phone = request.data.get('email_phone')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not all([email_phone, new_password, confirm_password]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)
        
        if is_valid_email(email_phone):
            try:
                vendor = Vendor.objects.get(email_address=email_phone)
                user = vendor.user
                user.set_password(new_password)
                user.save()

                OTP.objects.filter(user=user).delete()

                return Response({"message": "Password updated successfully!"}, status=status.HTTP_200_OK)

            except Vendor.DoesNotExist:
                return Response({"error": "Vendor with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                vendor = User.objects.get(mobile=email_phone)
                vendor.set_password(new_password)
                vendor.save()

                OTP.objects.filter(user=vendor).delete()

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
            return PackageCategory.objects.get(pk=pk)
        except PackageCategory.DoesNotExist:
            return None





    def get(self, request, pk):  
        subcategories = PackageSubCategory.objects.filter(category_id=pk)
        if not subcategories.exists():
            return Response({"error": "No subcategories found for this category."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageSubCategorySerializer(subcategories, many=True)
        return Response({"subcategories": serializer.data}, status=status.HTTP_200_OK)




# PACKAGE CRUD
class PackageAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]  
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 

  
    def get(self, request, package_id=None):
        print('lates workng2')
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





class DayPlanDeleteAPIView(APIView):
    parser_classes = [JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, day_id):
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get the day plan ensuring it belongs to the vendor
        day_plan = get_object_or_404(DayPlan, pk=day_id, package__vendor=vendor)

        day_plan.delete()
        return Response({"message": "Day plan deleted successfully."}, status=status.HTTP_204_NO_CONTENT)




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







class DayPlanCreateAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

  

    # def post(self, request, package_id):
    #     try:
    #         data = request.data
    #         files = request.FILES
    #         day_number = int(data.get("day"))

    #         package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
    #         if not package:
    #             return Response({"error": "Package not found"}, status=404)

    #         with transaction.atomic():
    #             day_plan = DayPlan.objects.create(package=package, day_number=day_number)

    #             # PLACE
    #             place = Place.objects.create(
    #                 day_plan=day_plan,
    #                 name=data.get("place_name"),
    #                 description=data.get("place_description")
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"place_image_{i}")
    #                 if img:
    #                     PlaceImage.objects.create(place=place, image=img)

    #             # STAY
    #             stay = Stay.objects.create(
    #                 day_plan=day_plan,
    #                 hotel_name=data.get("hotel_name"),
    #                 description=data.get("description"),
    #                 location=data.get("location"),
    #                 is_ac=data.get("is_ac") == "true",
    #                 has_breakfast=data.get("has_breakfast") == "true"
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"stay_image_{i}")
    #                 if img:
    #                     StayImage.objects.create(stay=stay, image=img)

    #             # MEAL
    #             meal = Meal.objects.create(
    #                 day_plan=day_plan,
    #                 type=data.get("meal_type"),
    #                 time=data.get("meal_time")
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"meal_image_{i}")
    #                 if img:
    #                     MealImage.objects.create(meal=meal, image=img)

    #             # ACTIVITY
    #             activity = Activity.objects.create(
    #                 day_plan=day_plan,
    #                 name=data.get("activity_name"),
    #                 description=data.get("activity_description")
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"activity_image_{i}")
    #                 if img:
    #                     ActivityImage.objects.create(activity=activity, image=img)

    #         return Response({"message": "Day plan added successfully."}, status=201)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=500)





    def post(self, request, package_id):
        try:
            data = request.data
            files = request.FILES
            day_number = int(data.get("day") or 1)

            description = data.get("description") or ''


            package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
            if not package:
                return Response({"error": "Package not found"}, status=404)

            with transaction.atomic():
                day_plan = DayPlan.objects.create(package=package, day_number=day_number,description=description)

                # PLACE
                place = Place.objects.create(
                    day_plan=day_plan,
                    name=data.get("place_name") or "",
                    description=data.get("place_description") or ""
                )
                for i in range(1, 5):
                    img = files.get(f"place_image_{i}")
                    if img:
                        PlaceImage.objects.create(place=place, image=img)

                # STAY
                stay = Stay.objects.create(
                    day_plan=day_plan,
                    hotel_name=data.get("hotel_name") or "",
                    # description=data.get("description") or "",
                    description=data.get("stay_description") or "",
                    location=data.get("location") or "",
                    is_ac=(data.get("is_ac") or "").lower() == "true",
                    has_breakfast=(data.get("has_breakfast") or "").lower() == "true"
                )
                for i in range(1, 5):
                    img = files.get(f"stay_image_{i}")
                    if img:
                        StayImage.objects.create(stay=stay, image=img)

                # MEAL
                meal_time_str = data.get("meal_time") or ""
                meal_time = None
                if meal_time_str:
                    try:
                        meal_time = datetime.strptime(meal_time_str.strip(), "%H:%M").time()
                    except ValueError:
                        return Response({"error": "Invalid meal_time format. Use HH:MM."}, status=400)

                meal = Meal.objects.create(
                    day_plan=day_plan,
                    type=data.get("meal_type") or "breakfast",
                    description=data.get("meal_description") or "",
                    restaurant_name=data.get("restaurant_name") or "",
                    location=data.get("meal_location") or "",
                    time=meal_time
                )
                for i in range(1, 5):
                    img = files.get(f"meal_image_{i}")
                    if img:
                        MealImage.objects.create(meal=meal, image=img)

                # ACTIVITY
                activity_time_str = data.get("activity_time") or ""
                activity_time = None
                if activity_time_str:
                    try:
                        activity_time = datetime.strptime(activity_time_str.strip(), "%H:%M").time()
                    except ValueError:
                        return Response({"error": "Invalid activity_time format. Use HH:MM."}, status=400)

                activity = Activity.objects.create(
                    day_plan=day_plan,
                    name=data.get("activity_name") or "",
                    description=data.get("activity_description") or "",
                    time=activity_time,
                    location=data.get("activity_location") or ""
                )
                for i in range(1, 5):
                    img = files.get(f"activity_image_{i}")
                    if img:
                        ActivityImage.objects.create(activity=activity, image=img)

            return Response({"message": "Day plan added successfully."}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)






    def get(self, request, day_plan_id):
        try:
            day_plan = DayPlan.objects.filter(id=day_plan_id, package__vendor__user=request.user).first()
            if not day_plan:
                return Response({"error": "Day Plan not found"}, status=404)

            serializer = DayPlanDetailSerializer(day_plan)
            return Response(serializer.data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)




class CreatePackageAndDayPlanAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]



    # def post(self, request):
    #     try:
    #         vendor = Vendor.objects.filter(user=request.user).first()
    #         if not vendor:
    #             return Response({"error": "Vendor not found"}, status=404)

    #         data = request.data
    #         files = request.FILES
    #         print(data.get("sub_category"),'inc'),

    #         def str_to_bool(value):
    #             return str(value).lower() in ['true', '1', 'yes']
            
    #         sub_category_id = data.get("sub_category")
    #         sub_category = PackageSubCategory.objects.get(id=sub_category_id)

    #         day_indices = set()
    #         for key in data.keys():
    #             match = re.search(r"_(\d+)$", key)
    #             if match:
    #                 day_indices.add(int(match.group(1)))
    #         total_days = len(day_indices)
    #         print(total_days,'days')
            

    #         # 1. CREATE PACKAGE
    #         package = Package.objects.create(
    #             vendor=vendor,
    #             places=data.get("places"),
    #             sub_category=sub_category,
    #             # description=data.get("description"),
    #             header_image=data.get("header_image"),
               
    #             days=total_days,
    #             extra_charge_per_km=data.get("extra_charge_per_km"),
    #             price_per_person=data.get("price_per_person"),
    #             bus_location=data.get("bus_location"),
    #             # ac_available=data.get("ac_available"),
    #             # guide_included=data.get("guide_included"),
    #             ac_available=str_to_bool(data.get("ac_available")),
    #             guide_included=str_to_bool(data.get("guide_included")),
    #             # longitude=data.get("longitude"),
    #             # latitude=data.get("latitude"),
    #         )

    #         # 2. SET BUSES
    #         buses_raw = data.getlist("buses")
    #         try:
    #             buses = [int(b) for b in json.loads(buses_raw[0])]
    #         except:
    #             buses = [int(b) for b in buses_raw]
    #         package.buses.set(buses)

    #         # 3. PACKAGE IMAGES
    #         if files.getlist("package_images"):
    #             for img in files.getlist("package_images"):
    #                 PackageImage.objects.create(package=package, image=img)

    #         # 4. DETECT AND HANDLE MULTIPLE DAYS
    #         day_indices = set()
    #         for key in data.keys():
    #             match = re.search(r"_(\d+)$", key)
    #             if match:
    #                 day_indices.add(int(match.group(1)))

    #         for day in sorted(day_indices):
    #             day_number = int(data.get(f"day_{day}", day))
    #             day_description = data.get(f"description_{day}", "")
    #             day_night = data.get(f"night_option_{day}", "")

            
    #             print(day_night,'nyt')

    #             day_plan = DayPlan.objects.create(
    #                 package=package,
    #                 day_number=day_number,
    #                 description=day_description,
    #                 night=str_to_bool(day_night)
    #             ) 
    #             print('after days')


    #             # --- PLACE ---
    #             place = Place.objects.create(
    #                 day_plan=day_plan,
    #                 name=data.get(f"place_name_{day}", ""),
    #                 description=data.get(f"place_description_{day}", "")
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"place_image_{day}_{i}")
    #                 if img:
    #                     PlaceImage.objects.create(place=place, image=img)

    #             # --- STAY ---
    #             stay = Stay.objects.create(
    #                 day_plan=day_plan,
    #                 hotel_name=data.get(f"stay_name_{day}", ""),
    #                 description=data.get(f"stay_description_{day}", ""),
    #                 location=data.get(f"location_{day}", ""),
    #                 is_ac=data.get(f"is_ac_{day}", "false").lower() == "true",
    #                 has_breakfast=data.get(f"has_breakfast_{day}", "false").lower() == "true"
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"stay_image_{day}_{i}")
    #                 if img:
    #                     StayImage.objects.create(stay=stay, image=img)

    #             # --- MEAL ---
    #             meal_time_str = data.get(f"meal_time_{day}")
    #             meal_time = None
    #             if meal_time_str and re.match(r"^\d{2}:\d{2}$", meal_time_str):
    #                 meal_time = datetime.strptime(meal_time_str, "%H:%M").time()

    #             meal = Meal.objects.create(
    #                 day_plan=day_plan,
    #                 type=data.get(f"meal_type_{day}", "breakfast"),
    #                 description=data.get(f"meal_description_{day}", ""),
    #                 restaurant_name=data.get(f"restaurant_name_{day}", ""),
    #                 location=data.get(f"meal_location_{day}", ""),
    #                 time=meal_time
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"meal_image_{day}_{i}")
    #                 if img:
    #                     MealImage.objects.create(meal=meal, image=img)

    #             # --- ACTIVITY ---
    #             activity_time_str = data.get(f"activity_time_{day}")
    #             activity_time = None
    #             if activity_time_str and re.match(r"^\d{2}:\d{2}$", activity_time_str):
    #                 activity_time = datetime.strptime(activity_time_str, "%H:%M").time()


    #             activity = Activity.objects.create(
    #                 day_plan=day_plan,
    #                 name=data.get(f"activity_name_{day}", ""),
    #                 description=data.get(f"activity_description_{day}", ""),
    #                 location=data.get(f"activity_location_{day}", ""),
    #                 time=activity_time
    #             )
    #             for i in range(1, 5):
    #                 img = files.get(f"activity_image_{day}_{i}")
    #                 if img:
    #                     ActivityImage.objects.create(activity=activity, image=img)

    #         return Response({"message": "Package created successfully with all day plans."}, status=201)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=500)




    def post(self, request):
        try:
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return Response({"error": "Vendor not found"}, status=404)

            data = request.data
            files = request.FILES

            def str_to_bool(value):
                return str(value).lower() in ['true', '1', 'yes']

            sub_category = PackageSubCategory.objects.get(id=data.get("sub_category"))

            # Detect total days
            day_indices = {
                int(re.search(r"_(\d+)", key).group(1))
                for key in data.keys()
                if re.search(r"_(\d+)", key)
            }
            total_days = len(day_indices)

            package = Package.objects.create(
                vendor=vendor,
                places=data.get("places"),
                sub_category=sub_category,
                header_image=data.get("header_image"),
                # days=total_days,
                days=data.get("days"),
                extra_charge_per_km=data.get("extra_charge_per_km"),
                price_per_person=data.get("price_per_person"),
                bus_location=data.get("bus_location"),
                ac_available=str_to_bool(data.get("ac_available")),
                guide_included=str_to_bool(data.get("guide_included")),
            )

            # Buses
            buses_raw = data.getlist("buses")
            try:
                buses = [int(b) for b in json.loads(buses_raw[0])]
            except:
                buses = [int(b) for b in buses_raw]
            package.buses.set(buses)

            # Package images
            for img in files.getlist("package_images"):
                PackageImage.objects.create(package=package, image=img)

            # Loop through days
            for day in sorted(day_indices):
                day_number = int(data.get(f"day_{day}", day))
                description = data.get(f"description_{day}", "")
                night = str_to_bool(data.get(f"night_option_{day}", ""))

                day_plan = DayPlan.objects.create(
                    package=package,
                    day_number=day_number,
                    description=description,
                    night=night
                )

                # --- Multiple Places ---
                place_keys = [k for k in data.keys() if k.startswith(f"place_name_{day}_")]
                for k in place_keys:
                    idx = k.split('_')[-1]
                    place = Place.objects.create(
                        day_plan=day_plan,
                        name=data.get(f"place_name_{day}_{idx}", ""),
                        description=data.get(f"place_description_{day}_{idx}", "")
                    )
                    for i in range(1, 5):
                        img = files.get(f"place_image_{day}_{idx}_{i}")
                        if img:
                            PlaceImage.objects.create(place=place, image=img)

                # --- Only One Stay ---
                if Stay.objects.filter(day_plan=day_plan).exists():
                    return Response({"error": f"A Stay already exists for Day {day}."}, status=400)

                stay = Stay.objects.create(
                    day_plan=day_plan,
                    hotel_name=data.get(f"stay_name_{day}", ""),
                    description=data.get(f"stay_description_{day}", ""),
                    location=data.get(f"location_{day}", ""),
                    is_ac=str_to_bool(data.get(f"is_ac_{day}", "false")),
                    has_breakfast=str_to_bool(data.get(f"has_breakfast_{day}", "false"))
                )
                for i in range(1, 5):
                    img = files.get(f"stay_image_{day}_{i}")
                    if img:
                        StayImage.objects.create(stay=stay, image=img)

                # --- Multiple Meals ---
                meal_keys = [k for k in data.keys() if k.startswith(f"meal_type_{day}_")]
                for k in meal_keys:
                    idx = k.split('_')[-1]
                   


                    meal_time = None  # Default

                    # Get the raw time string
                    raw_meal_time_str = data.get(f"meal_time_{day}_{idx}", "")

                    if raw_meal_time_str:
                        # Clean any invisible characters and whitespace
                        meal_time_str = raw_meal_time_str.strip().replace('\u200e', '').replace('\u200f', '')

                        print(repr(meal_time_str), 'repr')

                        # Check format and try to parse
                        if re.match(r"^\d{2}:\d{2}$", meal_time_str):
                            try:
                                meal_time = datetime.strptime(meal_time_str, "%H:%M").time()
                            except ValueError as e:
                                print(f"Time parsing error for '{meal_time_str}': {e}")
                    else:
                        print(f"No valid meal_time_str for {day=} {idx=}")


                    print(meal_time,'time')


                    meal = Meal.objects.create(
                        day_plan=day_plan,
                        type=data.get(f"meal_type_{day}_{idx}", "breakfast"),
                        description=data.get(f"meal_description_{day}_{idx}", ""),
                        restaurant_name=data.get(f"restaurant_name_{day}_{idx}", ""),
                        location=data.get(f"meal_location_{day}_{idx}", ""),
                        time=meal_time
                    )
                    for i in range(1, 5):
                        img = files.get(f"meal_image_{day}_{idx}_{i}")
                        if img:
                            MealImage.objects.create(meal=meal, image=img)

                # --- Multiple Activities ---
                activity_keys = [k for k in data.keys() if k.startswith(f"activity_name_{day}_")]
                for k in activity_keys:
                    idx = k.split('_')[-1]
                    activity_time_str = data.get(f"activity_time_{day}_{idx}")
                    activity_time = datetime.strptime(activity_time_str, "%H:%M").time() if activity_time_str and re.match(r"^\d{2}:\d{2}$", activity_time_str) else None

                    activity = Activity.objects.create(
                        day_plan=day_plan,
                        name=data.get(f"activity_name_{day}_{idx}", ""),
                        description=data.get(f"activity_description_{day}_{idx}", ""),
                        location=data.get(f"activity_location_{day}_{idx}", ""),
                        time=activity_time
                    )
                    for i in range(1, 5):
                        img = files.get(f"activity_image_{day}_{idx}_{i}")
                        if img:
                            ActivityImage.objects.create(activity=activity, image=img)

            return Response({"message": "Package created successfully with all details."}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

















class EditDayPlanAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, day_id):
        try:
            day_plan = DayPlan.objects.filter(id=day_id, package__vendor__user=request.user).first()
            if not day_plan:
                return Response({"error": "DayPlan not found or access denied"}, status=404)

            data = request.data
            files = request.FILES

            day_plan.description = data.get("description", day_plan.description)
            day_plan.save()

            # ----------------- PLACE -----------------
            place = day_plan.places.first()
            place.name = data.get("place_name", place.name)
            place.description = data.get("place_description", place.description)
            place.save()

            for key in files:
                if key.startswith("place_images_"):
                    try:
                        img_id = int(key.split("_")[-1])
                        img_obj = PlaceImage.objects.get(id=img_id, place=place)
                        img_obj.image = files[key]
                        img_obj.save()
                    except PlaceImage.DoesNotExist:
                        continue

            for img in files.getlist("new_place_images"):
                PlaceImage.objects.create(place=place, image=img)

            # ----------------- STAY -----------------
#             if files.getlist("place_images"):
#                 place.images.all().delete()
#                 for img in files.getlist("place_images"):
#                     PlaceImage.objects.create(place=place, image=img)


            stay = day_plan.stay
            stay.hotel_name = data.get("stay_name", stay.hotel_name)
            stay.description = data.get("stay_description", stay.description)
            stay.location = data.get("location", stay.location)
            stay.is_ac = data.get("is_ac", str(stay.is_ac)).lower() == "true"
            stay.has_breakfast = data.get("has_breakfast", str(stay.has_breakfast)).lower() == "true"
            stay.save()

            for key in files:
                if key.startswith("stay_images_"):
                    try:
                        img_id = int(key.split("_")[-1])
                        img_obj = StayImage.objects.get(id=img_id, stay=stay)
                        img_obj.image = files[key]
                        img_obj.save()
                    except StayImage.DoesNotExist:
                        continue

            for img in files.getlist("new_stay_images"):
                StayImage.objects.create(stay=stay, image=img)

            # ----------------- MEAL -----------------
            meal = day_plan.meals.first()
            meal_time_str = data.get("meal_time")
            if meal_time_str:
                meal.time = datetime.strptime(meal_time_str, "%H:%M").time()
            meal.type = data.get("meal_type", meal.type)
            meal.description = data.get("meal_description", meal.description)
            meal.restaurant_name = data.get("restaurant_name", meal.restaurant_name)
            meal.location = data.get("meal_location", meal.location)
            meal.save()

            for key in files:
                if key.startswith("meal_images_"):
                    try:
                        img_id = int(key.split("_")[-1])
                        img_obj = MealImage.objects.get(id=img_id, meal=meal)
                        img_obj.image = files[key]
                        img_obj.save()
                    except MealImage.DoesNotExist:
                        continue

            for img in files.getlist("new_meal_images"):
                MealImage.objects.create(meal=meal, image=img)

            # ----------------- ACTIVITY -----------------
            activity = day_plan.activities.first()
            activity_time_str = data.get("activity_time")
            if activity_time_str:
                activity.time = datetime.strptime(activity_time_str, "%H:%M").time()
            activity.name = data.get("activity_name", activity.name)
            activity.description = data.get("activity_description", activity.description)
            activity.location = data.get("activity_location", activity.location)
            activity.save()

            for key in files:
                if key.startswith("activity_images_"):
                    try:
                        img_id = int(key.split("_")[-1])
                        img_obj = ActivityImage.objects.get(id=img_id, activity=activity)
                        img_obj.image = files[key]
                        img_obj.save()
                    except ActivityImage.DoesNotExist:
                        continue

            for img in files.getlist("new_activity_images"):
                ActivityImage.objects.create(activity=activity, image=img)

            return Response({"message": "Day plan updated successfully."}, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)






class AddDayPlanAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

   

    # def post(self, request, package_id):
    #     try:
    #         package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
    #         if not package:
    #             return Response({"error": "Package not found or access denied"}, status=404)

    #         data = request.data
    #         files = request.FILES

         



    #         # Get next day number
    #         last_day = DayPlan.objects.filter(package=package).order_by("-day_number").first()
    #         next_day_number = last_day.day_number + 1 if last_day else 1
    #         suffix = f"_{next_day_number}"  # e.g. _3

    #         print("Files received:", list(files.keys()))
    #         print("Data received:", data)
    #         print("Data Keys:", list(data.keys()))
    #         print("Place Name:", data.get(f"place_name{suffix}"))
    #         print("Stay Name:", data.get(f"stay_name{suffix}"))
    #         print("Meal Type:", data.get(f"meal_type{suffix}"))
    #         print("Activity Name:", data.get(f"activity_name{suffix}"))


    #         day_description = data.get(f"description{suffix}", "")
    #         day_plan = DayPlan.objects.create(
    #             package=package,
    #             day_number=next_day_number,
    #             description=day_description
    #         )

    #         # Place
    #         place = Place.objects.create(
    #             day_plan=day_plan,
    #             name=data.get(f"place_name_{suffix}", ""),
    #             description=data.get(f"place_description_{suffix}", "")
    #         )
    #         self._upload_images(files, f"place_image{suffix}", place)

    #         # Stay
    #         stay = Stay.objects.create(
    #             day_plan=day_plan,
    #             hotel_name=data.get(f"stay_name{suffix}", ""),
    #             description=data.get(f"stay_description{suffix}", ""),
    #             location=data.get(f"location{suffix}", ""),
    #             is_ac=data.get(f"is_ac{suffix}", "false").lower() == "true",
    #             has_breakfast=data.get(f"has_breakfast{suffix}", "false").lower() == "true"
    #         )
    #         self._upload_images(files, f"stay_image{suffix}", stay)

    #         # Meal
    #         meal_time_str = data.get(f"meal_time{suffix}")
    #         meal_time = datetime.strptime(meal_time_str, "%H:%M").time() if meal_time_str else None
    #         meal = Meal.objects.create(
    #             day_plan=day_plan,
    #             type=data.get(f"meal_type{suffix}", "breakfast"),
    #             description=data.get(f"meal_description{suffix}", ""),
    #             restaurant_name=data.get(f"restaurant_name{suffix}", ""),
    #             location=data.get(f"meal_location{suffix}", ""),
    #             time=meal_time
    #         )
    #         self._upload_images(files, f"meal_image{suffix}", meal)

    #         # Activity
    #         activity_time_str = data.get(f"activity_time{suffix}")
    #         activity_time = datetime.strptime(activity_time_str, "%H:%M").time() if activity_time_str else None
    #         activity = Activity.objects.create(
    #             day_plan=day_plan,
    #             name=data.get(f"activity_name{suffix}", ""),
    #             description=data.get(f"activity_description{suffix}", ""),
    #             location=data.get(f"activity_location{suffix}", ""),
    #             time=activity_time
    #         )
    #         self._upload_images(files, f"activity_image{suffix}", activity)

    #         return Response({"message": "Day plan added successfully."}, status=201)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=500)



   

    def _upload_images(self, files, prefix, related_obj_index, related_obj):
        # images keys look like: place_image_0_0, place_image_0_1, etc.
        for img_index in range(4):  # up to 4 images per object
            key = f"{prefix}_{related_obj_index}_{img_index}"
            img = files.get(key)
            if img:
                if isinstance(related_obj, Place):
                    PlaceImage.objects.create(place=related_obj, image=img)
                elif isinstance(related_obj, Stay):
                    StayImage.objects.create(stay=related_obj, image=img)
                elif isinstance(related_obj, Meal):
                    MealImage.objects.create(meal=related_obj, image=img)
                elif isinstance(related_obj, Activity):
                    ActivityImage.objects.create(activity=related_obj, image=img)


    # def post(self, request, package_id):
    #     try:
    #         package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
    #         if not package:
    #             return Response({"error": "Package not found or access denied"}, status=404)

    #         data = request.data
    #         files = request.FILES

    #         # Determine next day number
    #         last_day = DayPlan.objects.filter(package=package).order_by("-day_number").first()
    #         next_day_number = last_day.day_number + 1 if last_day else 1

    #         # Create DayPlan
    #         day_description = data.get("description", "")
    #         day_plan = DayPlan.objects.create(
    #             package=package,
    #             day_number=next_day_number,
    #             description=day_description
    #         )

    #         # Create multiple Places using indexed fields
    #         place_index = 1
    #         while True:
    #             place_name_key = f"place_name_{place_index}"
    #             place_description_key = f"place_description_{place_index}"
    #             image_key = f"place_image_{place_index}"

    #             if place_name_key not in data:
    #                 break  # Exit loop if no more places

    #             place = Place.objects.create(
    #                 day_plan=day_plan,
    #                 name=data.get(place_name_key, ""),
    #                 description=data.get(place_description_key, "")
    #             )
    #             self._upload_images(files, image_key, place)
    #             place_index += 1

    #         # Create Stay
    #         stay = Stay.objects.create(
    #             day_plan=day_plan,
    #             hotel_name=data.get("stay_name", ""),
    #             description=data.get("stay_description", ""),
    #             location=data.get("location", ""),
    #             is_ac=data.get("is_ac", "false").lower() == "true",
    #             has_breakfast=data.get("has_breakfast", "false").lower() == "true"
    #         )
    #         self._upload_images(files, "stay_image", stay)

    #         # Create Meal
    #         meal_time_str = data.get("meal_time")
    #         meal_time = datetime.strptime(meal_time_str, "%H:%M").time() if meal_time_str else None

    #         meal = Meal.objects.create(
    #             day_plan=day_plan,
    #             type=data.get("meal_type", "breakfast"),
    #             description=data.get("meal_description", ""),
    #             restaurant_name=data.get("restaurant_name", ""),
    #             location=data.get("meal_location", ""),
    #             time=meal_time
    #         )
    #         self._upload_images(files, "meal_image", meal)

    #         # Create Activity
    #         activity_time_str = data.get("activity_time")
    #         activity_time = datetime.strptime(activity_time_str, "%H:%M").time() if activity_time_str else None

    #         activity = Activity.objects.create(
    #             day_plan=day_plan,
    #             name=data.get("activity_name", ""),
    #             description=data.get("activity_description", ""),
    #             location=data.get("activity_location", ""),
    #             time=activity_time
    #         )
    #         self._upload_images(files, "activity_image", activity)

    #         return Response({"message": "Day plan added successfully."}, status=201)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=500)


    def post(self, request, package_id):
        try:
            package = Package.objects.filter(id=package_id, vendor__user=request.user).first()
            if not package:
                return Response({"error": "Package not found or access denied"}, status=404)

            data = request.data
            files = request.FILES

            last_day = DayPlan.objects.filter(package=package).order_by("-day_number").first()
            next_day_number = last_day.day_number + 1 if last_day else 1

            # Create DayPlan
            day_description = data.get("description", "")
            day_plan = DayPlan.objects.create(
                package=package,
                day_number=next_day_number,
                description=day_description
            )

            # --------- HANDLE PLACES ---------
            places = json.loads(data.get("places", "[]"))
            for idx, place_data in enumerate(places):
                place = Place.objects.create(
                    day_plan=day_plan,
                    name=place_data.get("name", ""),
                    description=place_data.get("description", "")
                )
                # self._upload_images(files, f"place_image_{idx}", place)
                self._upload_images(files, "place_image", idx, place)

            # --------- HANDLE STAY ---------
            stay_list = json.loads(data.get("stay", "[]"))
            if stay_list:
                stay_data = stay_list[0]
                stay = Stay.objects.create(
                    day_plan=day_plan,
                    hotel_name=stay_data.get("hotel_name", ""),
                    description=stay_data.get("description", ""),
                    location=stay_data.get("location", ""),
                    is_ac=stay_data.get("is_ac", False),
                    has_breakfast=stay_data.get("has_breakfast", False)
                )
                # self._upload_images(files, "stay_image", stay)
                self._upload_images(files, "stay_image", 0, stay)

            # --------- HANDLE MEAL ---------
            meal_list = json.loads(data.get("meal", "[]"))
            if meal_list:
                meal_data = meal_list[0]
                meal_time = datetime.strptime(meal_data.get("time", ""), "%H:%M").time() if meal_data.get("time") else None
                meal = Meal.objects.create(
                    day_plan=day_plan,
                    type=meal_data.get("type", "breakfast"),
                    description=meal_data.get("description", ""),
                    restaurant_name=meal_data.get("restaurant_name", ""),
                    location=meal_data.get("location", ""),
                    time=meal_time
                )
                # self._upload_images(files, "meal_image", meal)
                self._upload_images(files, "meal_image", 0, meal)

            # --------- HANDLE ACTIVITY ---------
            activity_list = json.loads(data.get("activity", "[]"))
            if activity_list:
                activity_data = activity_list[0]
                activity_time = datetime.strptime(activity_data.get("time", ""), "%H:%M").time() if activity_data.get("time") else None
                activity = Activity.objects.create(
                    day_plan=day_plan,
                    name=activity_data.get("name", ""),
                    description=activity_data.get("description", ""),
                    location=activity_data.get("location", ""),
                    time=activity_time
                )
                # self._upload_images(files, "activity_image", activity)
                self._upload_images(files, "activity_image", 0, activity)

            return Response({"message": "Day plan added successfully."}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)





 

 




    def get(self, request, package_id, day_number):
        try:
            day_plan = DayPlan.objects.filter(
                package__id=package_id,
                package__vendor__user=request.user,
                day_number=day_number
            ).first()

            if not day_plan:
                return Response({"error": "Day plan not found"}, status=404)

            serializer = DayPlanSerializer(day_plan)
            return Response(serializer.data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


















class PackageEditAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser, FormParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, package_id):
        try:
            package = Package.objects.get(id=package_id, vendor__user=request.user)
        except ObjectDoesNotExist:
            return Response({"error": "Package not found or access denied."}, status=HTTP_404_NOT_FOUND)

        data = request.data
        files = request.FILES

        # Update fields
        package.places = data.get("places", package.places)
        package.days = data.get("days", package.days)
        package.nights = data.get("nights", package.nights)
        package.ac_available = data.get("ac_available", str(package.ac_available)).lower() == "true"
        package.guide_included = data.get("guide_included", str(package.guide_included)).lower() == "true"
        package.bus_location = data.get("bus_location", package.bus_location)
        package.price_per_person = data.get("price_per_person", package.price_per_person)
        package.extra_charge_per_km = data.get("extra_charge_per_km", package.extra_charge_per_km)
        package.status = data.get("status", package.status)

        # Handle image update
        if 'header_image' in files:
            package.header_image = files['header_image']

        # Handle buses (ManyToMany)
        if 'buses' in data:
            bus_ids = data.getlist('buses')
            package.buses.set(bus_ids)

        package.save()

        return Response({"message": "Package updated successfully."}, status=HTTP_200_OK)





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
            serializer = VendorUpdateSerializer(vendor, data=request.data, partial=True)
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

        # Include ALL bookings regardless of payment_status
        bus_revenue = BusBooking.objects.filter(
            bus__vendor=vendor,
            trip_status='ongoing'
        ).aggregate(total=Sum('total_amount'), count=Count('id'))

        package_revenue = PackageBooking.objects.filter(
            package__vendor=vendor,trip_status='ongoing'
        ).aggregate(total=Sum('total_amount'), count=Count('id'))

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
            created_at__year=current_year,
            trip_status='ongoing'
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
            created_at__year=current_year,
            trip_status='ongoing'
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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]



    



    def get(self, request):
        user = request.user

        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            return Response({"message": "Vendor profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Filter only ongoing bookings
        latest_bus = BusBooking.objects.filter(
            bus__vendor=vendor,
            trip_status='ongoing'
        ).order_by('-created_at').first()

        latest_package = PackageBooking.objects.filter(
            package__vendor=vendor,
            trip_status='ongoing'
        ).order_by('-created_at').first()

        # Find the latest one among them
        latest = max(
            filter(None, [latest_bus, latest_package]),
            key=lambda x: x.created_at,
            default=None
        )

        if not latest:
            return Response({"message": "No ongoing bookings found for the current vendor."}, status=status.HTTP_200_OK)

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
        
        bookings = BusBooking.objects.filter(bus__vendor=vendor,trip_status='ongoing')
        for booking in bookings:
            print("Booking created at:", booking.created_at)

        
        monthly_bookings = bookings.filter(
            created_at__year=current_year,
            created_at__month=current_month
        )
        
        total = monthly_bookings.aggregate(total=Sum('total_amount'))['total']
        monthly_revenue = float(total) if total else 0.0
        monthly_booking_count = monthly_bookings.count()

        serializer = BusBookingDetailSerializer(bookings, many=True)

        print("Vendor:", vendor)
        print("Total Bookings:", bookings.count())
        print("Monthly Bookings:", monthly_bookings.count())


        
        return Response({
            "bookings": serializer.data,
            "monthly_revenue": monthly_revenue,
            "monthly_booking_count": monthly_booking_count
        }, status=status.HTTP_200_OK)





    

class BusBookingDetailView(APIView):
    """API View to get full details of a single bus booking"""

 
    def get(self, request, booking_id, format=None):
        try:
            booking = BusBooking.objects.get(id=booking_id)
        except BusBooking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

  

        # Serialize and return
        serializer = BusBookingDetailSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)












class BusHistoryFilterView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

  

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
            bus__vendor=vendor,
            trip_status='ongoing'
        )

        serializer = BusBookingDetailSerializer(bookings, many=True)

        current_year = timezone.now().year
        current_month = timezone.now().month

        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor,trip_status='ongoing')

         


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

        latest_booking = PackageBooking.objects.filter(user=user,trip_status='ongoing').order_by('-id').first()
        
        if not latest_booking:
            return Response({"message": "No package bookings found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageBookingDetailSerializer(latest_booking)
        return Response(serializer.data, status=status.HTTP_200_OK)
    





class BusBookingEarningsHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
 

    def get(self, request):
        try:
            vendor = request.user.vendor    

            vendor_buses = Bus.objects.filter(vendor=vendor)

            bookings = BusBooking.objects.filter(bus__in=vendor_buses,trip_status='ongoing').order_by('-start_date')

            serializer = BusBookingBasicSerializer(bookings, many=True)

            total_revenue = bookings.aggregate(total=Sum('total_amount'))['total'] or 0

            now = timezone.now()

            monthly_bookings = bookings.filter(created_at__year=now.year, created_at__month=now.month)

            monthly_revenue = monthly_bookings.aggregate(total=Sum('total_amount'))['total'] or 0
            monthly_revenue = float(monthly_revenue)

            monthly_booking_count = monthly_bookings.count()

            return Response({
                "earnings": serializer.data,
                "total_revenue": total_revenue,
                "monthly_revenue": monthly_revenue,
                "monthly_booking_count": monthly_booking_count  
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






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

            package_bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing').order_by('-start_date')

            total_revenue = package_bookings.aggregate(total_revenue=Sum('total_amount'))['total_revenue'] or 0.00

            current_month = datetime.now().month

            monthly_bookings = package_bookings.filter(start_date__month=current_month)

            monthly_revenue = monthly_bookings.aggregate(monthly_revenue=Sum('total_amount'))['monthly_revenue'] or 0.00

            monthly_booking_count = monthly_bookings.count()

            if monthly_booking_count == 0:
                monthly_revenue = 0.00

            serializer = PackageBookingEarnigsSerializer(package_bookings, many=True)

            return Response({
                "earnings": serializer.data,
                "total_revenue": total_revenue,
                "monthly_revenue": monthly_revenue,
                "monthly_booking_count": monthly_booking_count
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PackageBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

   



    def get(self, request, format=None):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=404)

        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing')

        monthly_bookings = bookings.filter(
            created_at__year=current_year,
            created_at__month=current_month
        )

        total = monthly_bookings.aggregate(total=Sum('total_amount'))['total']
        monthly_revenue = float(total) if total else 0.0
        
        monthly_count = monthly_bookings.count()

        serializer = PackageBookingDetailSerializer(monthly_bookings, many=True)

        return Response({
            "bookings": serializer.data,
            "monthly_revenue": monthly_revenue,
            "monthly_booking_count": monthly_count   
        }, status=200)











class SinglePackageBookingDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        print(booking_id)
        try:
            package_booking = PackageBooking.objects.get(id=booking_id,)
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
            start_date__lte=end_date,
            trip_status='ongoing'
        )
        
        serializer = PackageBookingDetailSerializer(package_bookings, many=True)

        current_year = timezone.now().year
        current_month = timezone.now().month

        all_user_bookings = PackageBooking.objects.filter(user=user,trip_status='ongoing')

         

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

        all_bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing') 
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
    #             busy_date = serializer.validated_data.get('date')
    #             from_time = serializer.validated_data.get('from_time')
    #             to_time = serializer.validated_data.get('to_time')

    #             if VendorBusyDate.objects.filter(
    #                 vendor=vendor, date=busy_date, from_time=from_time, to_time=to_time
    #             ).exists():
    #                 return Response({
    #                     "message": "Busy date already exists for this date and time.",
    #                     "data": {}
    #                 }, status=status.HTTP_200_OK)

    #             busy_date_instance = VendorBusyDate.objects.create(
    #                 vendor=vendor,
    #                 date=busy_date,
    #                 from_time=from_time,
    #                 to_time=to_time,
    #                 reason=serializer.validated_data.get('reason')
    #             )

    #             buses = serializer.validated_data.get('buses')
    #             busy_date_instance.buses.set(buses)

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
                from_time = serializer.validated_data.get('from_time')
                to_time = serializer.validated_data.get('to_time')

                if VendorBusyDate.objects.filter(
                    vendor=vendor, date=busy_date, from_time=from_time, to_time=to_time
                ).exists():
                    return Response({
                        "message": "Busy date already exists for this date and time.",
                        "data": {}
                    }, status=status.HTTP_200_OK)

                busy_date_instance = VendorBusyDate.objects.create(
                    vendor=vendor,
                    date=busy_date,
                    from_time=from_time,
                    to_time=to_time,
                    reason=serializer.validated_data.get('reason')
                )

                bus_ids = serializer.validated_data.get('bus_ids', [])
                busy_date_instance.buses.set(bus_ids)

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



    def get(self, request):
        vendor = request.user.vendor
        vendor_buses = Bus.objects.filter(vendor=vendor)
        bookings = BusBooking.objects.filter(bus__in=vendor_buses,trip_status='ongoing').order_by('-created_at')

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

        total_revenue = BusBooking.objects.filter(bus__in=vendor_buses,trip_status='ongoing').aggregate(
            total=Sum('total_amount'))['total'] or 0

        first_day_of_month = today.replace(day=1)
        month_start = make_aware(datetime.combine(first_day_of_month, datetime.min.time()))
        monthly_revenue = BusBooking.objects.filter(
            bus__in=vendor_buses, created_at__gte=month_start,
            trip_status='ongoing'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        monthly_revenue = float(monthly_revenue)

        serializer = BusBookingBasicSerializer(bookings, many=True)

        return Response({
            "earnings": serializer.data,
            "total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue
        })





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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

   



    
    def get(self, request):
        vendor = request.user.vendor
        print(vendor.full_name)

        now = timezone.now()
        current_year = now.year
        current_month = now.month

        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor,trip_status='ongoing')

        monthly_revenue = float(
            all_vendor_bookings.filter(
                created_at__year=current_year,
                created_at__month=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )

        canceled_bookings = BusBooking.objects.filter(
            bus__vendor=vendor,trip_status='ongoing'
        ).filter(
            Q(payment_status='cancelled') | Q(trip_status='cancelled')
        ).order_by('-created_at')

        monthly_booking_count = all_vendor_bookings.filter(
            created_at__year=current_year,
            created_at__month=current_month
        ).count()

        serializer = BusBookingDetailSerializer222(canceled_bookings, many=True)

        return Response({
            "canceled_bus_bookings": serializer.data,
            "monthly_revenue": monthly_revenue,
            "monthly_booking_count": monthly_booking_count
        }, status=status.HTTP_200_OK)






class CanceledBusBookingFilterView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id=None):
        vendor = request.user.vendor
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        all_vendor_bookings = BusBooking.objects.filter(bus__vendor=vendor,trip_status='ongoing')

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

        canceled_bookings = BusBooking.objects.filter(
            Q(bus__vendor=vendor) & cancel_filter
        )

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

        all_vendor_package_bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing')

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
                package__vendor=vendor,
                trip_status='ongoing'
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

        all_vendor_package_bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing')

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

        queryset = PackageBooking.objects.filter(cancel_conditions, package__vendor=vendor,trip_status='ongoing')

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
                trip_status='ongoing',
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
                bus__vendor=vendor,
                trip_status='ongoing'
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

    def post(self, request, booking_id1):
        try:
            vendor = request.user.vendor
            # bus_booking = BusBooking.objects.get(id=booking_id, bus__vendor=vendor)
            bus_booking = BusBooking.objects.get(booking_id=booking_id1, bus__vendor=vendor)


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

    def get(self, request, booking_id1):
        try:
            vendor = request.user.vendor   
            bus_booking = BusBooking.objects.filter(
                booking_id=booking_id1, 
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

    def post(self, request, booking_id1):
        print('is working',booking_id1)
        try:
            vendor = request.user.vendor   
            # package_booking = PackageBooking.objects.filter(
            #     id=booking_id, 
            #     booking_status='pending',   
            #     package__vendor=vendor   
            # ).first()
            package_booking = PackageBooking.objects.filter(
                booking_id=booking_id1, 
                booking_status='pending',   
                package__vendor=vendor ,
                trip_status='ongoing'  
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

    def get(self, request, booking_id1):
        try:
            vendor = request.user.vendor   
            package_booking = PackageBooking.objects.filter(
                booking_id=booking_id1, 
                booking_status='accepted',   
                package__vendor=vendor,
                trip_status='ongoing'
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
                trip_status='ongoing',  
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
                package__vendor=vendor,
                trip_status='ongoing'
            )

            serializer = PackageBookingListSerializer(declined_bookings, many=True)

            return Response({"declined_bookings": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)







class DeclineBusBookingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id1):
        try:
            vendor = request.user.vendor
            bus_booking = BusBooking.objects.get(booking_id=booking_id1, bus__vendor=vendor)

            if bus_booking.booking_status != 'pending':
                return Response({"error": "Booking is already accepted or declined."}, status=status.HTTP_400_BAD_REQUEST)

            cancellation_reason = request.data.get('cancellation_reason')

            if not cancellation_reason:
                return Response({"error": "Cancellation reason is required."}, status=status.HTTP_400_BAD_REQUEST)

            bus_booking.booking_status = 'declined'
            bus_booking.trip_status = 'cancelled'
            bus_booking.cancellation_reason = cancellation_reason
            bus_booking.save()

            return Response({
                "message": "Bus booking has been declined successfully.",
                "cancellation_reason": cancellation_reason
            }, status=status.HTTP_200_OK)

        except BusBooking.DoesNotExist:
            return Response({"error": "Bus booking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)








class DeclinePackageBookingView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, booking_id1):
        try:
            vendor = request.user.vendor
            package_booking = PackageBooking.objects.get(booking_id=booking_id1, package__vendor=vendor)

            if package_booking.booking_status != 'pending':
                return Response({"error": "Booking is already accepted or declined."}, status=status.HTTP_400_BAD_REQUEST)

            reason = request.data.get('cancellation_reason', '').strip()
            if not reason:
                return Response({"error": "Cancelation reason is required."}, status=status.HTTP_400_BAD_REQUEST)

            package_booking.booking_status = 'declined'
            package_booking.trip_status = 'cancelled'
            package_booking.cancellation_reason = reason
            package_booking.save()

            return Response({
                "message": "Package booking declined successfully.",
                "cancellation_reason": reason
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
                booking_status='pending',
                trip_status='ongoing'
            ).order_by('-created_at')

            confirmed_bookings = BusBooking.objects.filter(
                bus__in=vendor_buses,
                booking_status='accepted',
                trip_status='ongoing'
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

    # def get(self, request):
    #     try:
    #         print('hello')
    #         vendor = request.user.vendor
    #         print(vendor)

    #         pending_bookings = PackageBooking.objects.filter(
    #             package__vendor=vendor,
    #             booking_status='pending'
    #         ).order_by('-created_at')

    #         accepted_bookings = PackageBooking.objects.filter(
    #             package__vendor=vendor,
    #             booking_status='accepted'
    #         ).order_by('-created_at')

    #         pending_serializer = PackageBookingREQUESTSerializer(pending_bookings, many=True)
    #         accepted_serializer = PackageBookingREQUESTSerializer(accepted_bookings, many=True)

    #         return Response({
    #             "pending_requests": pending_serializer.data,
    #             "confirmed_bookings": accepted_serializer.data
    #         }, status=status.HTTP_200_OK)

    #     except Exception as e:
    #         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            print('hello')
            vendor = request.user.vendor
            print(vendor)

            pending_bookings = PackageBooking.objects.filter(
                package__vendor=vendor,
                booking_status='pending',
                trip_status='ongoing'
            ).order_by('-created_at')

            accepted_bookings = PackageBooking.objects.filter(
                package__vendor=vendor,
                booking_status='accepted',
                trip_status='ongoing'
            ).order_by('-created_at')

            pending_serializer = PackageBookingREQUESTSerializer(pending_bookings, many=True)
            accepted_serializer = PackageBookingREQUESTSerializer(accepted_bookings, many=True)

            return Response({
                "pending_requests": pending_serializer.data,
                "confirmed_bookings": accepted_serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)








# class VendorLatestSingleBookingHistoryView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

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

    def get(self, request, booking_id1):
        try:
            vendor = request.user.vendor

            # Try BusBooking first
            bus_booking = BusBooking.objects.filter(
                booking_id=booking_id1,
                bus__vendor=vendor,
                booking_status='pending'   
            ).first()

            if bus_booking:
                data = {
                    "booking_type": "bus",
                    "from_location": bus_booking.from_location,
                    "to_location": bus_booking.to_location,
                    "start_date": bus_booking.start_date,
                    "end_date": bus_booking.end_date,
                    "total_travelers": bus_booking.total_travelers,
                    "male": bus_booking.male,
                    "female": bus_booking.female,
                    "children": bus_booking.children,
                    "stops": BusBookingStopSerializer(bus_booking.stops.all(), many=True, read_only=True).data,
                    "travelers": TravelerSerializer(bus_booking.travelers.all(), many=True).data
                }
                return Response(data, status=status.HTTP_200_OK)

            # Then try PackageBooking
            package_booking = PackageBooking.objects.filter(
                booking_id=booking_id1,
                package__vendor=vendor,
                booking_status='pending'
            ).first()

            if package_booking:
                night_count = package_booking.package.day_plans.filter(night=True).count()
                total_days = package_booking.package.days + night_count
                end_date = package_booking.start_date + timedelta(days=total_days)
                data = {
                    "booking_type": "package",
                    "from_location": package_booking.from_location,
                    "to_location": package_booking.to_location,
                    "start_date": package_booking.start_date,
                    "end_date":end_date,
                    "total_travelers": package_booking.total_travelers,
                    "male": package_booking.male,
                    "female": package_booking.female,
                    "children": package_booking.children,
                    "rooms":package_booking.rooms,
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

    def get(self, request, booking_id1):
        try:
            print('is working',booking_id1)
            vendor = request.user.vendor

            

            # Try to find a matching BusBooking
            bus_booking = BusBooking.objects.filter(booking_id=booking_id1, bus__vendor=vendor).first()
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
                    "paid_amount": bus_booking.paid_amount,
                    "balance_amount": bus_booking.balance_amount,
                }
                return Response(data, status=status.HTTP_200_OK)

            # Try to find a matching PackageBooking
            package_booking = PackageBooking.objects.filter(booking_id=booking_id1, package__vendor=vendor).first()
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
                    "paid_amount": package_booking.paid_amount,
                    "balance_amount": package_booking.balance_amount,
                }
                return Response(data, status=status.HTTP_200_OK)

            return Response({"message": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)







class PackageUpdateAPIView(APIView):
    def put(self, request, pk):
        package = get_object_or_404(Package, pk=pk)
        serializer = PackageSerializer(package, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    





class VendorTransactionHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # def get(self, request):
    #     try:
    #         vendor = Vendor.objects.get(user=request.user)
    #     except Vendor.DoesNotExist:
    #         return Response({"error": "Vendor not found."}, status=404)

    #     transactions = BusBooking.objects.filter(
    #         bus__vendor=vendor,
    #         payment_status__in=['partial', 'paid']
    #     ).order_by('-created_at')

    #     serializer = BaseBookingSerializer(transactions, many=True)
    #     return Response(serializer.data, status=200)


    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=404)

        # Fetch Bus Bookings
        bus_bookings = BusBooking.objects.filter(
            bus__vendor=vendor,
            payment_status__in=['partial', 'paid'],
            trip_status='ongoing'
        ).order_by('-created_at')

        serializer = BaseBookingSerializer(all_bookings, many=True)
        return Response(serializer.data, status=200)







class DeleteVendorAccountView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request):
        print('is working')
        user = request.user

        if user.role != User.VENDOR:
            return Response(
                {"error": "Only vendors can delete their account."},
                status=status.HTTP_403_FORBIDDEN
            )

        vendor = get_object_or_404(Vendor, user=user)
        
        user.delete()

        return Response({"message": "Vendor account deleted successfully."}, status=status.HTTP_204_NO_CONTENT)








from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import requests

def get_access_token():
    url = "https://production.deepvue.tech/v1/authorize"
    payload = {
        'client_id': '2732a5119a',
        'client_secret': '26fbe96efaf24488b16ef65acdb869ea'
    }

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("access_token")
    except requests.exceptions.RequestException as e:
        print("Error fetching access token:", e)
        return None

class VehicleRCVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        rc_number = request.data.get("rc_number")
        input_chassis = request.data.get("vehicle_chasi_number")
        input_engine = request.data.get("vehicle_engine_number")

        if not rc_number or not input_chassis or not input_engine:
            return Response(
                {"error": "rc_number, vehicle_chasi_number, and vehicle_engine_number are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        access_token = get_access_token()
        if not access_token:
            return Response(
                {"error": "Failed to retrieve access token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        url = f"https://production.deepvue.tech/v1/verification/rc-advanced?rc_number={rc_number}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'x-api-key': '26fbe96efaf24488b16ef65acdb869ea',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                fetched_chassis = data.get("data", {}).get("vehicle_chasi_number", "").strip().upper()
                fetched_engine = data.get("data", {}).get("vehicle_engine_number", "").strip().upper()

                input_chassis = input_chassis.strip().upper()
                input_engine = input_engine.strip().upper()

                mismatches = {}
                if input_chassis != fetched_chassis:
                    mismatches["chassis_mismatch"] = {
                        "input": input_chassis
                    }
                if input_engine != fetched_engine:
                    mismatches["engine_mismatch"] = {
                        "input": input_engine
                    }

                if mismatches:
                    return Response(
                        {
                            "status": "verification_failed",
                            "mismatches": mismatches,
                            "full_data": data
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    return Response(
                        {
                            "status": "verification_successful",
                            "message": "Chassis number and engine number match",
                            "full_data": data
                        },
                        status=status.HTTP_200_OK
                    )
            else:
                return Response(
                    {
                        "error": "Verification failed",
                        "status_code": response.status_code,
                        "details": response.text
                    },
                    status=response.status_code
                )

        except requests.exceptions.RequestException as e:
            return Response(
                {"error": "Request failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )