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
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser
from .models import AdminCommissionSlab, AdminCommission
from .serializers import AdminCommissionSlabSerializer, AdminCommissionSerializer
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from collections import defaultdict
from datetime import date
from django.core.paginator import Paginator
from rest_framework import status as http_status
from itertools import chain
from django.db.models import Count
from itertools import chain
from operator import attrgetter
from django.db.models.functions import TruncMonth

from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa

import io



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
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


    def get(self, request, user_id=None):
        if user_id:
            try:
                



                # user = User.objects.get(id=user_id, role=User.USER)
                user = User.objects.filter(role=User.USER).order_by('-created_at')  # or '-created_at'

                serializer = UserSerializer(user)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User not found or not a normal user."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # users = User.objects.filter(role=User.USER)
            users = User.objects.filter(role=User.USER).order_by('-created_at')

            booked_users_bus = BusBooking.objects.values('user_id')
            booked_users_package = PackageBooking.objects.values('user_id')

            booked_user_ids = set([user['user_id'] for user in booked_users_bus] + [user['user_id'] for user in booked_users_package])
            booked_users = User.objects.filter(id__in=booked_user_ids, role=User.USER)

            active_users = User.objects.filter(role=User.USER, is_active=True)

            inactive_users = User.objects.filter(role=User.USER, is_active=False)

            serializer = UserSerializer(users, many=True)

            return Response({
                "total_users": users.count(),
                "booked_users_count": booked_users.count(),
                "active_users_count": active_users.count(),
                "inactive_users_count": inactive_users.count(),
                "users": serializer.data
            }, status=status.HTTP_200_OK)













# VENDOR CREATING AND LISTING
class AdminCreateVendorAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = AdminVendorSerializer(data=request.data)
        if serializer.is_valid():
            vendor = serializer.save()
            return Response({
                "message": "Vendor created successfully by admin",
                "data": AdminVendorSerializer(vendor).data
            }, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    


    # def get(self, request):
    #     vendors = Vendor.objects.all()
    #     serializer = VendorFullSerializer(vendors, many=True)
    #     return Response({
    #         "message": "List of all vendors1",
    #         "data": serializer.data
    #     }, status=status.HTTP_200_OK)

    def get(self, request):
        vendors = Vendor.objects.all().order_by('-created_at')
        serializer = VendorFullSerializer(vendors, many=True)
        return Response({
            "message": "List of all vendors",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


# VENDOR DETAILS
class AdminVendorDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, vendor_id):
        try:
            print('vendor single')
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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
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
# class AdminBusDetailAPIView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#     def get(self, request, bus_id):
#         try:
#             bus = Bus.objects.get(pk=bus_id)
#         except Bus.DoesNotExist:
#             return Response({"error": "Bus not found"}, status=status.HTTP_404_NOT_FOUND)

#         serializer = BusDetailSerializer(bus)
#         return Response({
#             "message": "Bus details retrieved successfully",
#             "data": serializer.data
#         }, status=status.HTTP_200_OK)
    




# VENDOR PACKAGE LISTING
class AdminVendorPackageListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, vendor_id):
        try:
            print('hello')
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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, package_id):
        try:
            print('hello')
            package = Package.objects.get(pk=package_id)
        except Package.DoesNotExist:
            return Response({"error": "Package not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPackageDetailSerializer(package)
        return Response({
            "message": "Package details retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    



class PackageCategoryListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        categories = PackageCategory.objects.all()
        serializer = PackageCategoryListSerializer(categories, many=True)
        return Response({
            "message": "Package categories listed successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)








class AdminCreateUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication] 

    def post(self, request):
        serializer = AdminCreateUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






# ADVERTISMENT CREATION
# class AllSectionsCreateView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]
#     parser_classes = [MultiPartParser, FormParser]

 




   

#     def post(self, request, *args, **kwargs):
#         try:
#             # 1. Advertisements
#             ads_data = []
#             i = 0
#             while f'advertisements-{i}-title' in request.data:
#                 ad = {
#                     'title': request.data.get(f'advertisements-{i}-title'),
#                     'subtitle': request.data.get(f'advertisements-{i}-subtitle'),
#                     'type': request.data.get(f'advertisements-{i}-type'),
#                     'image': request.FILES.get(f'advertisements-{i}-image')
#                 }
#                 ads_data.append(ad)
#                 i += 1

#             ad_instances = []
#             for ad in ads_data:
#                 serializer = AdvertisementSerializer(data=ad)
#                 if serializer.is_valid():
#                     instance = serializer.save()
#                     ad_instances.append(instance)
#                 else:
#                     return Response({'error': serializer.errors}, status=400)

#             # 2. Limited Deals

#             deals_data = []
#             i = 0
#             while f'limited_deals-{i}-title' in request.data:
#                 deal = {
#                     'title': request.data.get(f'limited_deals-{i}-title'),
#                     'offer': request.data.get(f'limited_deals-{i}-offer'),
#                     'terms_and_conditions': request.data.get(f'limited_deals-{i}-terms_and_conditions'),
#                     'images': request.FILES.getlist(f'limited_deals-{i}-images'),
#                 }
#                 deals_data.append(deal)
#                 i += 1

#             for deal in deals_data:
#                 images = deal.pop('images', [])
#                 serializer = LimitedDealSerializer(data=deal)
#                 if serializer.is_valid():
#                     limited_deal = serializer.save()
#                     for img in images:
#                         LimitedDealImage.objects.create(deal=limited_deal, image=img)
#                 else:
#                     return Response({'error': serializer.errors}, status=400)

#             # 3. Footer Sections

#             footers_data = []
#             i = 0
#             while f'footer_sections-{i}-image' in request.FILES:
#                 footer = {
#                     'image': request.FILES.get(f'footer_sections-{i}-image'),
#                     'package': request.data.get(f'footer_sections-{i}-package')  # ID expected
#                 }
#                 footers_data.append(footer)
#                 i += 1

#             for footer in footers_data:
#                 serializer = FooterSectionSerializer(data=footer)
#                 if serializer.is_valid():
#                     serializer.save()
#                 else:
#                     return Response({'error': serializer.errors}, status=400)

#             # 4. Refer and Earn
#             if 'refer_and_earn-image' in request.FILES and 'refer_and_earn-price' in request.data:
#                 refer_data = {
#                     'image': request.FILES.get('refer_and_earn-image'),
#                     'price': request.data.get('refer_and_earn-price')
#                 }
#                 refer_serializer = ReferAndEarnSerializer(data=refer_data)
#                 if refer_serializer.is_valid():
#                     refer_serializer.save()
#                 else:
#                     return Response({'error': refer_serializer.errors}, status=400)

#             return Response({"message": "All data saved successfully!"}, status=201)

#         except Exception as e:
#             print(f"Error: {str(e)}")
#             return Response({"error": str(e)}, status=400)


  
#     def put(self, request, *args, **kwargs):
#         try:
#             # 1. Update Advertisements
#             i = 0
#             while f'advertisements-{i}-id' in request.data:
#                 ad_id = request.data.get(f'advertisements-{i}-id')
#                 ad_instance = Advertisement.objects.get(id=ad_id)
#                 ad_data = {
#                     'title': request.data.get(f'advertisements-{i}-title'),
#                     'description': request.data.get(f'advertisements-{i}-description'),
#                 }
#                 if request.FILES.get(f'advertisements-{i}-image'):
#                     ad_data['image'] = request.FILES.get(f'advertisements-{i}-image')

#                 serializer = AdvertisementSerializer(ad_instance, data=ad_data, partial=True)
#                 if serializer.is_valid():
#                     serializer.save()
#                 else:
#                     return Response({'error': serializer.errors}, status=400)
#                 i += 1

#             # 2. Update Limited Deals
#             i = 0
#             while f'limited_deals-{i}-id' in request.data:
#                 deal_id = request.data.get(f'limited_deals-{i}-id')
#                 deal_instance = LimitedDeal.objects.get(id=deal_id)

#                 deal_data = {
#                     'title': request.data.get(f'limited_deals-{i}-title'),
#                     'description': request.data.get(f'limited_deals-{i}-description'),
#                 }

#                 deal_serializer = LimitedDealSerializer(deal_instance, data=deal_data, partial=True)
#                 if deal_serializer.is_valid():
#                     updated_deal = deal_serializer.save()
#                 else:
#                     return Response({'error': deal_serializer.errors}, status=400)

#                 # Add new images if provided
#                 images = request.FILES.getlist(f'limited_deals-{i}-images')
#                 for img in images:
#                     LimitedDealImage.objects.create(deal=updated_deal, image=img)

#                 i += 1

#             # 3. Update Footer Sections
#             i = 0
#             while f'footer_sections-{i}-id' in request.data:
#                 footer_id = request.data.get(f'footer_sections-{i}-id')
#                 footer_instance = FooterSection.objects.get(id=footer_id)

#                 footer_data = {
#                     'title': request.data.get(f'footer_sections-{i}-title'),
#                     'description': request.data.get(f'footer_sections-{i}-description'),
#                 }

#                 if request.FILES.get(f'footer_sections-{i}-image'):
#                     footer_data['image'] = request.FILES.get(f'footer_sections-{i}-image')

#                 footer_serializer = FooterSectionSerializer(footer_instance, data=footer_data, partial=True)
#                 if footer_serializer.is_valid():
#                     footer_serializer.save()
#                 else:
#                     return Response({'error': footer_serializer.errors}, status=400)

#                 i += 1

#             return Response({"message": "All data updated successfully!"}, status=200)

#         except Exception as e:
#             print(f"Update Error: {str(e)}")
#             return Response({"error": str(e)}, status=400)





  
#     def put(self, request, *args, **kwargs):
#         try:
#             # 1. Update Advertisements
#             i = 0
#             while f'advertisements-{i}-id' in request.data:
#                 ad_id = request.data.get(f'advertisements-{i}-id')
#                 ad_instance = Advertisement.objects.get(id=ad_id)
#                 ad_data = {
#                     'title': request.data.get(f'advertisements-{i}-title'),
#                     'description': request.data.get(f'advertisements-{i}-description'),
#                 }
#                 if request.FILES.get(f'advertisements-{i}-image'):
#                     ad_data['image'] = request.FILES.get(f'advertisements-{i}-image')

#                 serializer = AdvertisementSerializer(ad_instance, data=ad_data, partial=True)
#                 if serializer.is_valid():
#                     serializer.save()
#                 else:
#                     return Response({'error': serializer.errors}, status=400)
#                 i += 1

#             # 2. Update Limited Deals
#             i = 0
#             while f'limited_deals-{i}-id' in request.data:
#                 deal_id = request.data.get(f'limited_deals-{i}-id')
#                 deal_instance = LimitedDeal.objects.get(id=deal_id)

#                 deal_data = {
#                     'title': request.data.get(f'limited_deals-{i}-title'),
#                     'description': request.data.get(f'limited_deals-{i}-description'),
#                 }

#                 deal_serializer = LimitedDealSerializer(deal_instance, data=deal_data, partial=True)
#                 if deal_serializer.is_valid():
#                     updated_deal = deal_serializer.save()
#                 else:
#                     return Response({'error': deal_serializer.errors}, status=400)

#                 # Add new images if provided
#                 images = request.FILES.getlist(f'limited_deals-{i}-images')
#                 for img in images:
#                     LimitedDealImage.objects.create(deal=updated_deal, image=img)

#                 i += 1

#             # 3. Update Footer Sections
#             i = 0
#             while f'footer_sections-{i}-id' in request.data:
#                 footer_id = request.data.get(f'footer_sections-{i}-id')
#                 footer_instance = FooterSection.objects.get(id=footer_id)

#                 footer_data = {
#                     'title': request.data.get(f'footer_sections-{i}-title'),
#                     'description': request.data.get(f'footer_sections-{i}-description'),
#                 }

#                 if request.FILES.get(f'footer_sections-{i}-image'):
#                     footer_data['image'] = request.FILES.get(f'footer_sections-{i}-image')

#                 footer_serializer = FooterSectionSerializer(footer_instance, data=footer_data, partial=True)
#                 if footer_serializer.is_valid():
#                     footer_serializer.save()
#                 else:
#                     return Response({'error': footer_serializer.errors}, status=400)

#                 i += 1

#             return Response({"message": "All data updated successfully!"}, status=200)

#         except Exception as e:
#             print(f"Update Error: {str(e)}")
#             return Response({"error": str(e)}, status=400)




#     def get(self, request, *args, **kwargs):
#         ads = Advertisement.objects.all()
#         ads_serialized = AdvertisementSerializer(ads, many=True).data

#         return Response({
#             "advertisements": ads_serialized
#         }, status=200)





class AdvertisementCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            ad = {
                'title': request.data.get('title'),
                'subtitle': request.data.get('subtitle'),
                'type': request.data.get('type'),
                'image': request.FILES.get('image')
            }
            serializer = AdvertisementSerializer(data=ad)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Advertisement saved successfully!'}, status=201)
            return Response({'error': serializer.errors}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)





class LimitedDealCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    

    def post(self, request, *args, **kwargs):
        try:
            deal_data = {
                'title': request.data.get('title'),
                'subtitle': request.data.get('subtitle'),
                'offer': request.data.get('offer'),
                'terms_and_conditions': request.data.get('terms_and_conditions'),
            }

            serializer = LimitedDealSerializer(data=deal_data)
            if serializer.is_valid():
                limited_deal = serializer.save()

                images = request.FILES.getlist('images')
                for image in images:
                    LimitedDealImage.objects.create(deal=limited_deal, image=image)

                return Response({"message": "Limited deal created successfully."}, status=201)

            return Response({'error': serializer.errors}, status=400)

        except Exception as e:
            return Response({"error": str(e)}, status=400)





class FooterSectionCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

   
    def post(self, request):
        try:
            main_image = request.FILES.get('main_image')
            if not main_image:
                return Response({'error': 'Main image is required.'}, status=400)

            extra_images = []
            for key in request.FILES:
                if key.startswith('image') and key != 'main_image':
                    extra_images.append(request.FILES[key])

            footer_data = {
                'main_image': main_image,
                'package': request.data.get('package')
            }
            footer_serializer = FooterSectionSerializer(data=footer_data)

            if footer_serializer.is_valid():
                footer = footer_serializer.save()

                for img in extra_images:
                    FooterImage.objects.create(footer_section=footer, image=img)

                return Response({'message': 'Footer section with images saved successfully!'}, status=201)

            return Response({'error': footer_serializer.errors}, status=400)

        except Exception as e:
            return Response({'error': str(e)}, status=400)




class ReferAndEarnCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            if ReferAndEarn.objects.exists():
                return Response({'error': 'A Refer and Earn entry already exists. Cannot add another one.'}, status=400)
            refer_data = {
                'image': request.FILES.get('image'),
                'price': request.data.get('price')
            }
            serializer = ReferAndEarnSerializer(data=refer_data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Refer and Earn saved successfully!'}, status=201)
            return Response({'error': serializer.errors}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)






class AdvertisementListView(APIView):
    def get(self, request, *args, **kwargs):
        advertisements = Advertisement.objects.all()
        serializer = AdvertisementSerializer(advertisements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




class AdvertisementDetailView(APIView):
    def get(self, request, ad_id, *args, **kwargs):
        try:
            advertisement = Advertisement.objects.get(id=ad_id)
        except Advertisement.DoesNotExist:
            return Response({"error": "Advertisement not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdvertisementSerializer(advertisement)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    def delete(self, request, ad_id, *args, **kwargs):
        try:
            advertisement = Advertisement.objects.get(id=ad_id)
        except Advertisement.DoesNotExist:
            return Response({"error": "Advertisement not found."}, status=status.HTTP_404_NOT_FOUND)

        advertisement.delete()
        return Response({"message": "Advertisement deleted successfully."}, status=status.HTTP_204_NO_CONTENT)



class LimitedDealListView(APIView):
    def get(self, request, *args, **kwargs):
        deals = LimitedDeal.objects.all()
        serializer = LimitedDealSerializer(deals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LimitedDealDetailView(APIView):
    def get(self, request, deal_id, *args, **kwargs):
        try:
            deal = LimitedDeal.objects.get(id=deal_id)
        except LimitedDeal.DoesNotExist:
            return Response({"error": "LimitedDeal not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = LimitedDealSerializer(deal)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def delete(self, request, deal_id, *args, **kwargs):
        try:
            deal = LimitedDeal.objects.get(id=deal_id)
        except LimitedDeal.DoesNotExist:
            return Response({"error": "LimitedDeal not found."}, status=status.HTTP_404_NOT_FOUND)

        deal.delete()
        return Response({"message": "LimitedDeal deleted successfully."}, status=status.HTTP_204_NO_CONTENT)




class FooterSectionListView(APIView):
    def get(self, request, *args, **kwargs):
        footers = FooterSection.objects.all()
        serializer = FooterSectionSerializer(footers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class FooterSectionDetailView(APIView):
    def get(self, request, footer_id, *args, **kwargs):
        try:
            footer = FooterSection.objects.get(id=footer_id)
        except FooterSection.DoesNotExist:
            return Response({"error": "FooterSection not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = FooterSectionSerializer(footer)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    def delete(self, request, footer_id, *args, **kwargs):
        try:
            footer = FooterSection.objects.get(id=footer_id)
        except FooterSection.DoesNotExist:
            return Response({"error": "FooterSection not found."}, status=status.HTTP_404_NOT_FOUND)

        footer.delete()
        return Response({"message": "FooterSection deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class ReferAndEarnListView(APIView):
    def get(self, request, *args, **kwargs):
        refs = ReferAndEarn.objects.all()
        serializer = ReferAndEarnSerializer(refs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ReferAndEarnDetailView(APIView):
    def get(self, request, ref_id, *args, **kwargs):
        try:
            ref = ReferAndEarn.objects.get(id=ref_id)
        except ReferAndEarn.DoesNotExist:
            return Response({"error": "ReferAndEarn not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReferAndEarnSerializer(ref)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    def delete(self, request, ref_id, *args, **kwargs):
        try:
            ref = ReferAndEarn.objects.get(id=ref_id)
        except ReferAndEarn.DoesNotExist:
            return Response({"error": "ReferAndEarn not found."}, status=status.HTTP_404_NOT_FOUND)

        ref.delete()
        return Response({"message": "ReferAndEarn entry deleted successfully."}, status=status.HTTP_204_NO_CONTENT)




    def patch(self, request, ref_id, *args, **kwargs):
        try:
            ref = ReferAndEarn.objects.get(id=ref_id)
        except ReferAndEarn.DoesNotExist:
            return Response({"error": "ReferAndEarn not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReferAndEarnSerializer(ref, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)








#EXPLROE CREATING
class ExploreSectionCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]




    def post(self, request, *args, **kwargs):
        data = request.data

        # 1. SIGHT DATA
        sight_data = {
            'title': data.get('sight[title]'),
            'description': data.get('sight[description]'),
            'season_description': data.get('sight[season_description]'),
        }

        sight_images = []
        index = 1
        while f'sight_image_{index}' in request.FILES:
            sight_images.append(request.FILES[f'sight_image_{index}'])
            index += 1

        # 2. EXPERIENCE DATA
        experience_data = []
        exp_index = 0
        while f'experiences[{exp_index}][description]' in data:
            exp = {
                'description': data.get(f'experiences[{exp_index}][description]'),
                'header': data.get(f'experiences[{exp_index}][header]'),
                'sub_header': data.get(f'experiences[{exp_index}][sub_header]'),
                'images': []
            }

            img_index = 0
            while f'experiences[{exp_index}][images][{img_index}]' in request.FILES:
                exp['images'].append(request.FILES[f'experiences[{exp_index}][images][{img_index}]'])
                img_index += 1

            experience_data.append(exp)
            exp_index += 1

        # 3. MULTIPLE SEASON DATA (max 3)
        seasons = []
        season_index = 0
        while f'season[{season_index}][from_date]' in data and season_index < 3:
            season_data = {
                'from_date': data.get(f'season[{season_index}][from_date]'),
                'to_date': data.get(f'season[{season_index}][to_date]'),
                'header': data.get(f'season[{season_index}][header]'),
                'icon1': data.get(f'season[{season_index}][icon1]'),
                'icon1_description': data.get(f'season[{season_index}][icon1_description]'),
                'icon2': data.get(f'season[{season_index}][icon2]'),
                'icon2_description': data.get(f'season[{season_index}][icon2_description]') or "",
                'icon3': data.get(f'season[{season_index}][icon3]'),
                'icon3_description': data.get(f'season[{season_index}][icon3_description]') or "",
            }
            seasons.append(season_data)
            season_index += 1

        # 4. SAVE DATA
        sight_serializer = SightSerializer(data=sight_data)
        if sight_serializer.is_valid():
            sight_instance = sight_serializer.save()

            for img in sight_images:
                SightImage.objects.create(sight=sight_instance, image=img)

            for exp in experience_data:
                exp_data = {
                    'description': exp['description'],
                    'header': exp['header'],
                    'sub_header': exp['sub_header'],
                }
                exp_serializer = ExperienceSerializer(data=exp_data)
                if exp_serializer.is_valid():
                    experience_instance = exp_serializer.save(sight=sight_instance)
                    for image in exp['images']:
                        ExperienceImage.objects.create(experience=experience_instance, image=image)
                else:
                    return Response({"error": exp_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            for season_data in seasons:
                season_data['sight'] = sight_instance.id
                season_serializer = SeasonTimeSerializer(data=season_data)
                if season_serializer.is_valid():
                    season_serializer.save(sight=sight_instance)
                else:
                    return Response({"error": season_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Sight, images, experiences, and up to 3 seasons created successfully!"}, status=status.HTTP_201_CREATED)

        return Response({"error": sight_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)








    # def put(self, request, *args, **kwargs):
    #     data = request.data
    #     sight_id = kwargs.get("pk")

    #     try:
    #         sight_instance = Sight.objects.get(id=sight_id)
    #     except Sight.DoesNotExist:
    #         return Response({"error": "Sight not found."}, status=status.HTTP_404_NOT_FOUND)

    #     # --- 1. Update Sight Fields if Present ---
    #     update_data = {}
    #     if data.get('sight[title]'): update_data['title'] = data.get('sight[title]')
    #     if data.get('sight[description]'): update_data['description'] = data.get('sight[description]')
    #     if data.get('sight[season_description]'): update_data['season_description'] = data.get('sight[season_description]')

    #     sight_serializer = SightSerializer(sight_instance, data=update_data, partial=True)
    #     if sight_serializer.is_valid():
    #         sight_serializer.save()
    #     else:
    #         return Response({"error": sight_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    #     # --- 2. Update Existing Sight Images if Present ---
    #     image_index = 0
    #     while True:
    #         image_id_key = f'sight_image[{image_index}][id]'  # e.g. sight_image[0][id]
    #         image_file_key = f'sight_image[{image_index}][file]'  # e.g. sight_image[0][file]
    #         if image_id_key in data and image_file_key in request.FILES:
    #             try:
    #                 img_id = int(data.get(image_id_key))
    #                 sight_image_instance = SightImage.objects.get(id=img_id, sight=sight_instance)
    #                 sight_image_instance.image = request.FILES[image_file_key]
    #                 sight_image_instance.save()
    #             except (SightImage.DoesNotExist, ValueError):
    #                 # Image not found or invalid ID, ignore or handle error
    #                 pass
    #             image_index += 1
    #         else:
    #             break

    #     # --- 3. Add New Experience(s) if Provided ---
    #     exp_index = 0
    #     while f'experiences[{exp_index}][description]' in data:
    #         exp_data = {
    #             'description': data.get(f'experiences[{exp_index}][description]'),
    #             'header': data.get(f'experiences[{exp_index}][header]'),
    #             'sub_header': data.get(f'experiences[{exp_index}][sub_header]')
    #         }
    #         exp_serializer = ExperienceSerializer(data=exp_data)
    #         if exp_serializer.is_valid():
    #             experience_instance = exp_serializer.save(sight=sight_instance)

    #             # Attach new images to this experience
    #             img_index = 0
    #             while f'experiences[{exp_index}][images][{img_index}]' in request.FILES:
    #                 ExperienceImage.objects.create(
    #                     experience=experience_instance,
    #                     image=request.FILES[f'experiences[{exp_index}][images][{img_index}]']
    #                 )
    #                 img_index += 1
    #         else:
    #             return Response({"error": exp_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    #         exp_index += 1

    #     # --- 4. Update Existing Season Entries if Provided ---
    #     season_index = 0
    #     while f'season[{season_index}][id]' in data and season_index < 3:
    #         try:
    #             season_id = int(data.get(f'season[{season_index}][id]'))
    #             season_instance = SeasonTime.objects.get(id=season_id, sight=sight_instance)
    #             season_data = {
    #                 'from_date': data.get(f'season[{season_index}][from_date]'),
    #                 'to_date': data.get(f'season[{season_index}][to_date]'),
    #                 'header': data.get(f'season[{season_index}][header]'),
    #                 'icon1': data.get(f'season[{season_index}][icon1]'),
    #                 'icon1_description': data.get(f'season[{season_index}][icon1_description]') or "",
    #                 'icon2': data.get(f'season[{season_index}][icon2]'),
    #                 'icon2_description': data.get(f'season[{season_index}][icon2_description]') or "",
    #                 'icon3': data.get(f'season[{season_index}][icon3]'),
    #                 'icon3_description': data.get(f'season[{season_index}][icon3_description]') or "",
    #             }
    #             season_serializer = SeasonTimeSerializer(season_instance, data=season_data, partial=True)
    #             if season_serializer.is_valid():
    #                 season_serializer.save()
    #             else:
    #                 return Response({"error": season_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    #         except (SeasonTime.DoesNotExist, ValueError):
    #             # Season not found or invalid ID, ignore or handle error
    #             pass
    #         season_index += 1

    #     return Response({"message": "Sight section updated successfully with partial data!"}, status=status.HTTP_200_OK)



    def put(self, request, *args, **kwargs):
        data = request.data
        sight_id = kwargs.get("pk")

        try:
            sight_instance = Sight.objects.get(id=sight_id)
        except Sight.DoesNotExist:
            return Response({"error": "Sight not found."}, status=status.HTTP_404_NOT_FOUND)

        # --- 1. Update Sight Fields if Present ---
        update_data = {}
        if data.get('sight[title]'): update_data['title'] = data.get('sight[title]')
        if data.get('sight[description]'): update_data['description'] = data.get('sight[description]')
        if data.get('sight[season_description]'): update_data['season_description'] = data.get('sight[season_description]')

        sight_serializer = SightSerializer(sight_instance, data=update_data, partial=True)
        if sight_serializer.is_valid():
            sight_serializer.save()
        else:
            return Response({"error": sight_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # --- 2. Update Existing Sight Images if Present ---
        image_index = 0
        while True:
            image_id_key = f'sight_image[{image_index}][id]'
            image_file_key = f'sight_image[{image_index}][file]'
            if image_id_key in data and image_file_key in request.FILES:
                try:
                    img_id = int(data.get(image_id_key))
                    sight_image_instance = SightImage.objects.get(id=img_id, sight=sight_instance)
                    sight_image_instance.image = request.FILES[image_file_key]
                    sight_image_instance.save()
                except (SightImage.DoesNotExist, ValueError):
                    pass
                image_index += 1
            else:
                break

        # --- 3. Update Existing Experiences if Provided ---
        exp_index = 0
        while f'experiences[{exp_index}][id]' in data:
            try:
                exp_id = int(data.get(f'experiences[{exp_index}][id]'))
                experience_instance = Experience.objects.get(id=exp_id, sight=sight_instance)

                exp_data = {
                    'description': data.get(f'experiences[{exp_index}][description]'),
                    'header': data.get(f'experiences[{exp_index}][header]'),
                    'sub_header': data.get(f'experiences[{exp_index}][sub_header]')
                }

                exp_serializer = ExperienceSerializer(experience_instance, data=exp_data, partial=True)
                if exp_serializer.is_valid():
                    experience_instance = exp_serializer.save()

                    # Add new images if provided
                    img_index = 0
                    while f'experiences[{exp_index}][images][{img_index}]' in request.FILES:
                        ExperienceImage.objects.create(
                            experience=experience_instance,
                            image=request.FILES[f'experiences[{exp_index}][images][{img_index}]']
                        )
                        img_index += 1
                else:
                    return Response({"error": exp_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            except (Experience.DoesNotExist, ValueError):
                pass
            exp_index += 1

        # --- 4. Update Existing Season Entries if Provided ---
        season_index = 0
        while f'season[{season_index}][id]' in data and season_index < 3:
            try:
                season_id = int(data.get(f'season[{season_index}][id]'))
                season_instance = SeasonTime.objects.get(id=season_id, sight=sight_instance)
                season_data = {
                    'from_date': data.get(f'season[{season_index}][from_date]'),
                    'to_date': data.get(f'season[{season_index}][to_date]'),
                    'header': data.get(f'season[{season_index}][header]'),
                    'icon1': data.get(f'season[{season_index}][icon1]'),
                    'icon1_description': data.get(f'season[{season_index}][icon1_description]') or "",
                    'icon2': data.get(f'season[{season_index}][icon2]'),
                    'icon2_description': data.get(f'season[{season_index}][icon2_description]') or "",
                    'icon3': data.get(f'season[{season_index}][icon3]'),
                    'icon3_description': data.get(f'season[{season_index}][icon3_description]') or "",
                }
                season_serializer = SeasonTimeSerializer(season_instance, data=season_data, partial=True)
                if season_serializer.is_valid():
                    season_serializer.save()
                else:
                    return Response({"error": season_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except (SeasonTime.DoesNotExist, ValueError):
                pass
            season_index += 1

        return Response({"message": "Sight section updated successfully with partial data!"}, status=status.HTTP_200_OK)





    def delete(self, request, *args, **kwargs):
        sight_id = kwargs.get('pk')   
        try:
            sight_instance = Sight.objects.get(pk=sight_id)
        except Sight.DoesNotExist:
            return Response({"error": "Sight not found."}, status=status.HTTP_404_NOT_FOUND)

        sight_instance.delete()  
        return Response({"message": "Sight and its experiences deleted successfully."}, status=status.HTTP_200_OK)









#EXPLORE LISTING
class ExploreSectionListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        sights = Sight.objects.all().order_by('-id')
        serializer = SightListSerializer(sights, many=True)
        return Response({"message": "Explore section fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

# EXPLORE DETAIL
class ExploreSectionDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, sight_id, *args, **kwargs):
        try:
            print('explroe details is workig')
            sight = Sight.objects.get(id=sight_id)
        except Sight.DoesNotExist:
            return Response({"error": "Sight not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SightListSerializer(sight)
        return Response({"message": "Explore section detail fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)




class AdminBookingListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        bus_bookings = list(BusBooking.objects.select_related('user').all())
        package_bookings = list(PackageBooking.objects.select_related('user', 'package').all())

        combined = bus_bookings + package_bookings
        combined_sorted = sorted(combined, key=lambda x: x.created_at, reverse=True)

        serializer = AdminBookingSerializer(combined_sorted, many=True)
        return Response(serializer.data)





# 🔹 List & Create Slabs
class AdminCommissionSlabListCreateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        slabs = AdminCommissionSlab.objects.all()
        serializer = AdminCommissionSlabSerializer(slabs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminCommissionSlabSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminCommissionSlabDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, pk):
        return get_object_or_404(AdminCommissionSlab, pk=pk)

    def get(self, request, pk):
        slab = self.get_object(pk)
        serializer = AdminCommissionSlabSerializer(slab)
        return Response(serializer.data)

    def put(self, request, pk):
        slab = self.get_object(pk)
        serializer = AdminCommissionSlabSerializer(slab, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        slab = self.get_object(pk)
        slab.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TotalAdminCommission(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        commissions = AdminCommission.objects.all().order_by('-created_at')
        serializer = AdminCommissionSerializer(commissions, many=True)

        total_revenue = commissions.aggregate(total=Sum('revenue_to_admin'))['total'] or 0

        bus_revenue = commissions.filter(booking_type='bus').aggregate(total=Sum('revenue_to_admin'))['total'] or 0
        package_revenue = commissions.filter(booking_type='package').aggregate(total=Sum('revenue_to_admin'))['total'] or 0

        commissions_by_date = defaultdict(float)
        for commission in commissions:
            day = commission.created_at.date()
            commissions_by_date[day] += float(commission.revenue_to_admin)

        revenue_by_date = [
            {'date': str(date_key), 'total_revenue': total}
            for date_key, total in commissions_by_date.items()
        ]

        return Response({
            'total_revenue': total_revenue,
            'bus_revenue': bus_revenue,
            'package_revenue': package_revenue,
            'revenue_by_date': revenue_by_date,
            'commissions': serializer.data
        })
    





class AdminPackageCategoryAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        categories = PackageCategory.objects.all()
        serializer = PackageCategorySerializer(categories, many=True)
        return Response({"message": "Package categories fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.is_staff:
            return Response({"error": "Only admin can create categories."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PackageCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Package Category created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        if not request.user.is_staff:
            return Response({"error": "Only admin can update categories."}, status=status.HTTP_403_FORBIDDEN)

        try:
            category = PackageCategory.objects.get(id=pk)
        except PackageCategory.DoesNotExist:
            return Response({"error": "Package Category not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageCategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Package Category updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response({"error": "Only admin can delete categories."}, status=status.HTTP_403_FORBIDDEN)

        try:
            category = PackageCategory.objects.get(id=pk)
        except PackageCategory.DoesNotExist:
            return Response({"error": "Package Category not found."}, status=status.HTTP_404_NOT_FOUND)

        category.delete()
        return Response({"message": "Package Category deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)





class AdminPackageSubCategoryAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self, pk):
        try:
            return PackageSubCategory.objects.get(pk=pk)
        except PackageSubCategory.DoesNotExist:
            return None

    def post(self, request):
        if not request.user.is_staff:
            return Response({"error": "Only admin users can create subcategories."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PackageSubCategorySerializer(data=request.data)
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

        # Filter by category_id if provided
        category_id = request.query_params.get('category_id')
        if category_id:
            subcategories = PackageSubCategory.objects.filter(category__id=category_id)
        else:
            subcategories = PackageSubCategory.objects.all()

        serializer = PackageSubCategorySerializer(subcategories, many=True)
        return Response({"subcategories": serializer.data}, status=status.HTTP_200_OK)













    def put(self, request, pk):
        if not request.user.is_staff:
            return Response({"error": "Only admin users can update subcategories."}, status=status.HTTP_403_FORBIDDEN)

        subcategory = self.get_object(pk)
        if not subcategory:
            return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageSubCategorySerializer(subcategory, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "SubCategory updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response({"error": "Only admin users can delete subcategories."}, status=status.HTTP_403_FORBIDDEN)

        subcategory = self.get_object(pk)
        if not subcategory:
            return Response({"error": "SubCategory not found."}, status=status.HTTP_404_NOT_FOUND)

        subcategory.delete()
        return Response({"message": "SubCategory deleted successfully!"}, status=status.HTTP_200_OK)









class AdminVendorOverview(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]



   

    def get(self, request):
        # vendors = Vendor.objects.all()
        vendors = Vendor.objects.all().order_by('-created_at')

        today = timezone.now().date()

        data = []

        for vendor in vendors:
            buses = Bus.objects.filter(vendor=vendor)
            packages = Package.objects.filter(vendor=vendor)

            bus_bookings = BusBooking.objects.filter(bus__vendor=vendor)
            package_bookings = PackageBooking.objects.filter(package__vendor=vendor)

            total_bookings = bus_bookings.count() + package_bookings.count()
            ongoing_bookings = bus_bookings.filter(start_date__gte=today).count() + \
                                package_bookings.filter(start_date__gte=today).count()

            total_earned = bus_bookings.aggregate(b=Sum('total_amount'))['b'] or 0
            total_earned += package_bookings.aggregate(p=Sum('total_amount'))['p'] or 0

            data.append({
                "vendor_id": vendor.pk,
                "vendor_name": vendor.full_name,
                "total_buses": buses.count(),
                "available_buses": buses.filter(status='available').count(),
                "booked_buses": buses.filter(status='booked').count(),
                "total_packages": packages.count(),
                "available_packages": packages.filter(status='available').count(),
                "booked_packages": packages.filter(status='booked').count(),
                "total_bookings": total_bookings,
                "ongoing_bookings": ongoing_bookings,
                "total_earned": total_earned,
            })


        page_number = request.query_params.get('page', 1)   
        paginator = Paginator(data, 6)   
        page_obj = paginator.get_page(page_number)

        return Response({
            'vendors': page_obj.object_list,  
            'count': paginator.count,  
            'num_pages': paginator.num_pages,   
            'current_page': page_obj.number,   
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,  
            'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None   
        })



class AllBookingsAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        package_bookings = PackageBooking.objects.get().all()
        bus_bookings = BusBooking.objects.get().all()

        package_serializer = AdminPackageBookingSerializer(package_bookings, many=True)
        bus_serializer = AdminBusBookingSerializer(bus_bookings, many=True)

        for item in package_serializer.data:
            item['booking_type'] = 'package'
        
        for item in bus_serializer.data:
            item['booking_type'] = 'bus'

        combined_data = list(chain(package_serializer.data, bus_serializer.data))

        sorted_combined_data = sorted(combined_data, key=lambda x: x['created_at'], reverse=True)

        return Response(sorted_combined_data)
    
class BookingDetails(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, booking_type, booking_id):
        if booking_type == 'bus':
            booking = get_object_or_404(BusBooking, id=booking_id)
            serializer = AdminBusBookingSerializer(booking)
        
        elif booking_type == 'package':
            booking = get_object_or_404(PackageBooking, id=booking_id)
            serializer = AdminPackageBookingSerializer(booking)
        
        else:
            return Response({'error': 'Invalid booking type.'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ListAllReviewsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Returns all bus reviews for admin view.
        """
        reviews = BusReview.objects.select_related('user', 'bus').order_by('-created_at')
        serializer = AdminBusReviewSerializer(reviews, many=True)

        return Response({
            "total_reviews": reviews.count(),
            "reviews": serializer.data
        }, status=status.HTTP_200_OK)






class RecentUsersAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]   

    def get(self, request):
        recent_users = User.objects.filter(role=User.USER).order_by('-created_at')[:10]  
        serializer = RecentUserSerializer(recent_users, many=True)
        return Response(serializer.data)








class TopVendorsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


    def get(self, request):
        bus_booking_counts = (
            BusBooking.objects
            .values('bus__vendor')
            .annotate(count=Count('id'))
        )
        bus_counts_map = {item['bus__vendor']: item['count'] for item in bus_booking_counts}

        package_booking_counts = (
            PackageBooking.objects
            .values('package__vendor')
            .annotate(count=Count('id'))
        )
        package_counts_map = {item['package__vendor']: item['count'] for item in package_booking_counts}

        total_counts = {}
        for vendor_id, count in bus_counts_map.items():
            total_counts[vendor_id] = total_counts.get(vendor_id, 0) + count
        for vendor_id, count in package_counts_map.items():
            total_counts[vendor_id] = total_counts.get(vendor_id, 0) + count

        vendors = Vendor.objects.filter(user__id__in=total_counts.keys())

        vendor_data = []
        for vendor in vendors:
            vendor_data.append({
                "name": vendor.full_name,
                "place": vendor.city,
                "total_booking_count": total_counts.get(vendor.user.id, 0)
            })

        vendor_data.sort(key=lambda x: x['total_booking_count'], reverse=True)

        serializer = TopVendorSerializer(vendor_data, many=True)
        return Response(serializer.data)





class SingleUserAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

   

    def get(self, request, user_id=None):
        try:
            user = User.objects.get(id=user_id, role=User.USER)

            personal_info = {
                'name': user.name,
                'phone_number': user.mobile,
                'email': user.email,
                'location': user.city,
                'address': user.address if hasattr(user, 'address') else "Not available"
            }

            bus_bookings = BusBooking.objects.filter(user=user)
            package_bookings = PackageBooking.objects.filter(user=user)

            all_bookings = list(bus_bookings) + list(package_bookings)

            rewards_count = user.rewards.count() if hasattr(user, 'rewards') else 0  

            total_booking_count = len(all_bookings)

            bus_booking_serializer = BusBookingSerializer08(bus_bookings, many=True)
            package_booking_serializer = PackageBookingSerializer08(package_bookings, many=True)

            combined_bookings = bus_booking_serializer.data + package_booking_serializer.data

            return Response({
                'personal_info': personal_info,
                'total_booking_count': total_booking_count,
                'rewards_count': rewards_count,
                'bookings': combined_bookings
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found or not a normal user."}, status=status.HTTP_404_NOT_FOUND)









class DashboardStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        today = date.today()

        total_bus_bookings = BusBooking.objects.count()
        total_package_bookings = PackageBooking.objects.count()
        total_bookings = total_bus_bookings + total_package_bookings

        today_bus_bookings = BusBooking.objects.filter(created_at__date=today).count()
        today_package_bookings = PackageBooking.objects.filter(created_at__date=today).count()
        today_bookings = today_bus_bookings + today_package_bookings

        total_vendors = Vendor.objects.count()
        total_users = User.objects.filter(role=User.USER).count()

        return Response({
            "total_bookings": total_bookings,
            "today_bookings": today_bookings,
            "total_vendors": total_vendors,
            "total_users": total_users
        })






class RecentApprovedBookingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        bus_bookings = BusBooking.objects.filter(booking_status='accepted').order_by('-created_at')[:5]
        package_bookings = PackageBooking.objects.filter(booking_status='accepted').order_by('-created_at')[:5]

        combined_bookings = sorted(
            chain(bus_bookings, package_bookings),
            key=attrgetter('created_at'),
            reverse=True
        )[:5]

        serializer = BookingDisplaySerializer(combined_bookings, many=True)
        return Response(serializer.data)


class CombinedBookingsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Fetch bookings
        bus_bookings = BusBooking.objects.all()
        package_bookings = PackageBooking.objects.all()

        # Annotate for distinguishing type (optional)
        for booking in bus_bookings:
            booking.booking_type = 'bus'
        for booking in package_bookings:
            booking.booking_type = 'package'
        
        # Combine and sort by created_at desc
        combined_bookings = sorted(
            chain(bus_bookings, package_bookings),
            key=attrgetter('created_at'),
            reverse=True
        )

        # Serialize each object based on type
        data = []
        for booking in combined_bookings:
            if booking.booking_type == 'bus':
                serializer = BusBookingSerializer(booking)
                serialized_data = serializer.data
                serialized_data['booking_type'] = 'bus'
                data.append(serialized_data)
            elif booking.booking_type == 'package':
                serializer = PackageBookingSerializer(booking)
                serialized_data = serializer.data
                serialized_data['booking_type'] = 'package'
                data.append(serialized_data)

        return Response(data, status=status.HTTP_200_OK)


class PaymentDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bus_bookings = BusBooking.objects.select_related('bus__vendor').all()
        package_bookings = PackageBooking.objects.select_related('package__vendor').all()

        data = []

        # Bus Booking Data
        for booking in bus_bookings:
            data.append({
                'id': booking.booking_id,
                'booking_type': 'Bus Booking',
                'vendor_name': booking.bus.vendor.full_name,
                'bus_or_package': booking.bus.bus_name,
                'total_amount': booking.total_amount,
                'advance_amount': booking.advance_amount,
                'payment_status': booking.payment_status,
            })

        # Package Booking Data
        for booking in package_bookings:
            data.append({
                'id': booking.booking_id,
                'booking_type': 'Package Booking',
                'vendor_name': booking.package.vendor.full_name,
                'bus_or_package': booking.package.places,
                'total_amount': booking.total_amount,
                'advance_amount': booking.advance_amount,
                'payment_status': booking.payment_status,
            })

        serializer = PaymentDetailsSerializer(data, many=True)
        return Response(serializer.data)


class SingleBookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_type, booking_id):
        if booking_type == 'bus':
            try:
                booking = BusBooking.objects.get(id=booking_id)
                serializer = BusBookingSerializer(booking)
                data = serializer.data
                data['booking_type'] = 'bus'
                return Response(data, status=status.HTTP_200_OK)
            except BusBooking.DoesNotExist:
                return Response({'detail': 'Bus Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        elif booking_type == 'package':
            try:
                booking = PackageBooking.objects.get(id=booking_id)
                serializer = PackageBookingSerializer(booking)
                data = serializer.data
                data['booking_type'] = 'package'
                return Response(data, status=status.HTTP_200_OK)
            except PackageBooking.DoesNotExist:
                return Response({'detail': 'Package Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        else:
            return Response({'detail': 'Invalid booking type.'}, status=status.HTTP_400_BAD_REQUEST)


class SinglePaymentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_type, booking_id):
        if booking_type == 'bus':
            try:
                booking = BusBooking.objects.select_related('bus__vendor').get(id=booking_id)
                data = {
                    'id': booking.booking_id,
                    'booking_type': 'Bus Booking',
                    'vendor_name': booking.bus.vendor.full_name,
                    'bus_or_package': booking.bus.bus_name,
                    'total_amount': booking.total_amount,
                    'advance_amount': booking.advance_amount,
                    'payment_status': booking.payment_status,
                }
                serializer = PaymentDetailsSerializer(data)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except BusBooking.DoesNotExist:
                return Response({'detail': 'Bus Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        elif booking_type == 'package':
            try:
                booking = PackageBooking.objects.select_related('package__vendor').get(id=booking_id)
                data = {
                    'id': booking.booking_id,
                    'booking_type': 'Package Booking',
                    'vendor_name': booking.package.vendor.full_name,
                    'bus_or_package': booking.package.places,
                    'total_amount': booking.total_amount,
                    'advance_amount': booking.advance_amount,
                    'payment_status': booking.payment_status,
                }
                serializer = PaymentDetailsSerializer(data)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except PackageBooking.DoesNotExist:
                return Response({'detail': 'Package Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        else:
            return Response({'detail': 'Invalid booking type.'}, status=status.HTTP_400_BAD_REQUEST)







class RevenueGraphView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bus_bookings = BusBooking.objects.all()
        package_bookings = PackageBooking.objects.all()

        all_bookings = list(bus_bookings) + list(package_bookings)

        bus_revenue = bus_bookings.annotate(month=TruncMonth('created_at')) \
                                  .values('month') \
                                  .annotate(total_amount=Sum('total_amount'))

        package_revenue = package_bookings.annotate(month=TruncMonth('created_at')) \
                                          .values('month') \
                                          .annotate(total_amount=Sum('total_amount'))

        monthly_data = {}

        for entry in list(bus_revenue) + list(package_revenue):
            month_str = entry['month'].strftime("%Y-%m")
            monthly_data[month_str] = monthly_data.get(month_str, 0) + float(entry['total_amount'])

        monthly_revenue = [{"month": k, "total_amount": v} for k, v in sorted(monthly_data.items())]

        def serialize_booking(b, booking_type):
            return {
                "id": b.id,
                "type": booking_type,
                "user": str(b.user),
                "start_date": b.start_date,
                "created_at": b.created_at,
                "total_amount": b.total_amount,
                "advance_amount": b.advance_amount,
                "payment_status": b.payment_status,
                "booking_status": b.booking_status,
                "trip_status": b.trip_status,
                "from_location": b.from_location,
                "to_location": b.to_location,
                "total_travelers": b.total_travelers
            }

        bookings_serialized = (
            [serialize_booking(b, "bus") for b in bus_bookings] +
            [serialize_booking(p, "package") for p in package_bookings]
        )

        return Response({
            "monthly_revenue": monthly_revenue,
            "all_bookings": bookings_serialized
        }, status=status.HTTP_200_OK)




class BusAdminAPIView(APIView):
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


    def get(self, request):
        if not request.user.is_superuser:
            return Response({'detail': 'Permission denied. Superuser access only.'},
                            status=status.HTTP_403_FORBIDDEN)

        buses = Bus.objects.all()
        serializer = BusAdminSerializerADMINBUSDETAILS(buses, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)





class SingleBusDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, bus_id):
        try:
            bus = Bus.objects.get(id=bus_id)
        except Bus.DoesNotExist:
            return Response({'detail': 'Bus not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BusAdminSerializerADMINBUSDETAILS(bus, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)




# class AdminPackageListView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         sub_category_id = request.query_params.get('sub_category_id')
#         if not sub_category_id:
#             return Response({"detail": "Sub category ID is required."}, status=400)

#         packages = Package.objects.filter(sub_category_id=sub_category_id).prefetch_related('buses__features', 'buses__vendor')
#         # serializer = PackageListSerializer(packages, many=True)
#         serializer = AdminPackageListSerializer(packages, many=True)
#         return Response(serializer.data)



class AdminPackageListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub_category_id = request.query_params.get('sub_category_id')

        if sub_category_id:
            packages = Package.objects.filter(sub_category_id=sub_category_id)
        else:
            packages = Package.objects.all()

        packages = packages.prefetch_related('buses__features', 'buses__vendor')
        serializer = AdminPackageListSerializer(packages, many=True)
        return Response(serializer.data, status=200)






class AdminPackageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            package = Package.objects.get(pk=pk)
        except Package.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPackageDetailSerializer(package, context={'request': request})
        return Response(serializer.data)









class AdminCreateUserAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






class ToggleUserActiveStatusAPIView(APIView):
    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        user.is_active = not user.is_active  # Toggle the value
        user.save()

        status_msg = "User is now active." if user.is_active else "User has been blocked."

        return Response({
            "user_id": user.id,
            "is_active": user.is_active,
            "message": status_msg
        }, status=status.HTTP_200_OK)






class AllUsersPDFAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        users = User.objects.filter(role=User.USER)
        booked_user_ids = set(
            list(BusBooking.objects.values_list('user_id', flat=True)) +
            list(PackageBooking.objects.values_list('user_id', flat=True))
        )
        booked_users = User.objects.filter(id__in=booked_user_ids, role=User.USER)
        active_users = users.filter(is_active=True)
        inactive_users = users.filter(is_active=False)

        context = {
            "total_users": users.count(),
            "booked_users_count": booked_users.count(),
            "active_users_count": active_users.count(),
            "inactive_users_count": inactive_users.count(),
            "users": users
        }

        # Render HTML to a string using a Django template
        html_string = render_to_string("users_report.html", context)

        # Create a file-like buffer
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)

        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="users_report.pdf"'
            return response
        else:
            return Response({"error": "PDF generation failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ToggleVendorStatusView(APIView):
    permission_classes = [IsAdminUser]   

    def post(self, request, vendor_id):
        vendor = get_object_or_404(User, id=vendor_id, role=User.VENDOR)
        vendor.is_active = not vendor.is_active
        vendor.save()
        return Response({
            'vendor_id': vendor.id,
            'name': vendor.name,
            'is_active': vendor.is_active,
            'message': 'Vendor status updated successfully.'
        }, status=status.HTTP_200_OK)


class BusReviewListView(APIView):
    def get(self, request):
        reviews = BusReview.objects.all().order_by('-created_at')
        serializer = BusReviewSerializer(reviews, many=True)
        return Response({"message": "Bus reviews fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)


class PackageReviewListView(APIView):
    def get(self, request):
        reviews = PackageReview.objects.all().order_by('-created_at')
        serializer = PackageReviewSerializer(reviews, many=True)
        return Response({"message": "Package reviews fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)





class AppReviewListView(APIView):
    def get(self, request):
        reviews = AppReview.objects.all().order_by('-created_at')
        serializer = AppReviewSerializer(reviews, many=True)
        return Response({"message": "App reviews fetched successfully!", "data": serializer.data}, status=status.HTTP_200_OK)


class AllReviewsListView(APIView):
    def get(self, request):
        bus_reviews = BusReview.objects.all().order_by('-created_at')
        package_reviews = PackageReview.objects.all().order_by('-created_at')
        app_reviews = AppReview.objects.all().order_by('-created_at')

        bus_serializer = BusReviewSerializer(bus_reviews, many=True)
        package_serializer = PackageReviewSerializer(package_reviews, many=True)
        app_serializer = AppReviewSerializer(app_reviews, many=True)

        return Response({
            "message": "All reviews fetched successfully!",
            "bus_reviews": bus_serializer.data,
            "package_reviews": package_serializer.data,
            "app_reviews": app_serializer.data,
        }, status=status.HTTP_200_OK)
    





class RecentReviewsAPIView(APIView):
    def get(self, request):
        bus_reviews = BusReview.objects.select_related('user', 'bus').all()
        package_reviews = PackageReview.objects.select_related('user', 'package').all()
        app_reviews = AppReview.objects.select_related('user').all()

        # Annotate each review with a type and related name (for frontend display)
        def annotate_reviews(queryset, type_label, get_related_name):
            for review in queryset:
                review.type = type_label
                review.related_name = get_related_name(review)
                yield review

        combined_reviews = list(chain(
            annotate_reviews(bus_reviews, "bus", lambda r: r.bus.bus_name),
            annotate_reviews(package_reviews, "package", lambda r: str(r.package)),
            annotate_reviews(app_reviews, "app", lambda r: "App Feedback")
        ))

        # Sort by created_at descending
        sorted_reviews = sorted(combined_reviews, key=attrgetter('created_at'), reverse=True)

        # Serialize manually using UnifiedReviewSerializer
        serialized = UnifiedReviewSerializer([
            {
                "user": review.user.name,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at,
                "profile_image":review.user.profile_image,
                "type": review.type,
                "related_name": review.related_name
            }
            for review in sorted_reviews
        ], many=True)

        return Response(serialized.data, status=status.HTTP_200_OK)








class TogglePopularStatusAPIView(APIView):
    def post(self, request, bus_id):
        try:
            bus = Bus.objects.get(id=bus_id)
            bus.is_popular = not bus.is_popular  # Toggle status
            bus.save()
            return Response({
                "message": "Popular status updated successfully.",
                "bus_id": bus.id,
                "is_popular": bus.is_popular
            }, status=status.HTTP_200_OK)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=status.HTTP_404_NOT_FOUND)




class AdminBusDeleteView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, pk):
        try:
            bus = Bus.objects.get(pk=pk)
            bus.delete()
            return Response({'message': 'Bus deleted successfully'}, status=status.HTTP_200_OK)
        except Bus.DoesNotExist:
            return Response({'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



class AdminPackageDeleteView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, pk):
        try:
            package = Package.objects.get(pk=pk)
            package.delete()
            return Response({'message': 'Package deleted successfully'}, status=status.HTTP_200_OK)
        except Package.DoesNotExist:
            return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)





class AmenityListCreateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        amenities = Amenity.objects.all()
        serializer = AmenitySerializer(amenities, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AmenitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AmenityRetrieveUpdateDeleteAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, pk):
        return get_object_or_404(Amenity, pk=pk)

    def get(self, request, pk):
        amenity = self.get_object(pk)
        serializer = AmenitySerializer(amenity)
        return Response(serializer.data)

    def put(self, request, pk):
        amenity = self.get_object(pk)
        serializer = AmenitySerializer(amenity, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        amenity = self.get_object(pk)
        amenity.delete()
        return Response(
        {"message": "Amenity deleted successfully."},
        status=status.HTTP_200_OK
    )





# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.models import ReferralRewardTransaction
from .serializers import ReferralRewardListSerializer, ReferralRewardDetailSerializer

class ReferralRewardListView(APIView):
    def get(self, request):
        rewards = ReferralRewardTransaction.objects.all().order_by('-created_at')
        serializer = ReferralRewardListSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReferralRewardDetailView(APIView):
    def get(self, request, id):
        try:
            reward = ReferralRewardTransaction.objects.get(id=id)
        except ReferralRewardTransaction.DoesNotExist:
            return Response({"error": "Reward not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReferralRewardDetailSerializer(reward)
        return Response(serializer.data, status=status.HTTP_200_OK)












class AdminPayoutRequestView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all payout requests for admin"""
        if request.user.role != 'admin':
            return Response({"error": "Access denied. Admin only."}, status=status.HTTP_403_FORBIDDEN)

        try:
            status_filter = request.query_params.get('status', None)
            payout_requests = PayoutRequest.objects.all()
            
            if status_filter:
                payout_requests = payout_requests.filter(status=status_filter)
            
            payout_requests = payout_requests.order_by('-created_at')
            
            payout_list = []
            for payout in payout_requests:
                payout_list.append({
                    'id': payout.id,
                    'vendor_name': payout.vendor.full_name,
                    'vendor_travels': payout.vendor.travels_name,
                    'request_amount': float(payout.request_amount),
                    'status': payout.status,
                    'remarks': payout.remarks,
                    'admin_remarks': payout.admin_remarks,
                    'transaction_id': payout.transaction_id,
                    'requested_at': payout.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'processed_at': payout.processed_at.strftime('%Y-%m-%d %H:%M:%S') if payout.processed_at else None,
                    'bank_detail': {
                        'holder_name': payout.bank_detail.holder_name,
                        'account_number': payout.bank_detail.account_number,
                        'ifsc_code': payout.bank_detail.ifsc_code,
                        'payout_mode': payout.bank_detail.payout_mode,
                        'phone_number': payout.bank_detail.phone_number,
                        'email_id': payout.bank_detail.email_id
                    }
                })

            return Response({
                "payout_requests": payout_list,
                "total_requests": len(payout_list)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, payout_id):
        """Update payout request status (approve/reject/process)"""
        if request.user.role != 'admin':
            return Response({"error": "Access denied. Admin only."}, status=status.HTTP_403_FORBIDDEN)

        try:
            payout_request = PayoutRequest.objects.get(id=payout_id)
            
            new_status = request.data.get('status')
            admin_remarks = request.data.get('admin_remarks', '')
            transaction_id = request.data.get('transaction_id', '')

            if new_status not in ['approved', 'rejected', 'processed']:
                return Response(
                    {"error": "Invalid status. Must be 'approved', 'rejected', or 'processed'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Handle wallet debit when payout is processed
            if new_status == 'processed' and payout_request.status != 'processed':
                # Get vendor wallet
                wallet, created = VendorWallet.objects.get_or_create(vendor=payout_request.vendor)
                
                # Debit amount from wallet
                try:
                    wallet.debit(
                        amount=payout_request.request_amount,
                        transaction_type='payout_processed',
                        reference_id=str(payout_request.id),
                        description=f"Payout processed - Request #{payout_request.id}"
                    )
                except ValueError as e:
                    return Response(
                        {"error": str(e)}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update payout request
            payout_request.status = new_status
            payout_request.admin_remarks = admin_remarks
            payout_request.processed_by = request.user
            
            if new_status == 'processed':
                payout_request.transaction_id = transaction_id
                payout_request.processed_at = timezone.now()

            payout_request.save()

            return Response({
                "message": f"Payout request {new_status} successfully.",
                "payout_request": {
                    'id': payout_request.id,
                    'vendor_name': payout_request.vendor.full_name,
                    'request_amount': float(payout_request.request_amount),
                    'status': payout_request.status,
                    'admin_remarks': payout_request.admin_remarks,
                    'transaction_id': payout_request.transaction_id,
                    'processed_at': payout_request.processed_at.strftime('%Y-%m-%d %H:%M:%S') if payout_request.processed_at else None
                }
            }, status=status.HTTP_200_OK)

        except PayoutRequest.DoesNotExist:
            return Response(
                {"error": "Payout request not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )