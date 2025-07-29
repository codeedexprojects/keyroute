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
from .serializers import AdminCommissionSlabSerializer, AdminCommissionSerializer,AdminEditBusSerializer
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
from rest_framework.pagination import PageNumberPagination
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.db.models import Q, Count

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
    







class VendorPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100 


class VendorListingPagination(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        vendors = Vendor.objects.select_related('user').prefetch_related(
            'bus_set', 'package_set'
        ).all().order_by('-created_at')
        
        # Apply filters and search
        vendors = self.apply_filters_and_search(vendors, request)
        
        paginator = VendorPagination()
        paginated_vendors = paginator.paginate_queryset(vendors, request)
        
        serializer = VendorFullSerializer(paginated_vendors, many=True)
        
        return paginator.get_paginated_response({
            "message": "List of all vendors",
            "data": serializer.data,
            "filters_applied": self.get_applied_filters(request)
        })
    
    def apply_filters_and_search(self, queryset, request):
        """Apply search and filter functionality"""
        
        # Search functionality
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(travels_name__icontains=search) |
                Q(full_name__icontains=search) |
                Q(email_address__icontains=search) |
                Q(user__mobile__icontains=search) |
                Q(location__icontains=search) |
                Q(city__icontains=search) |
                Q(address__icontains=search)
            )
        
        # Location filters - Fixed field references
        state = request.query_params.get('state', None)
        if state:
            # Use vendor's state field, not user's state
            queryset = queryset.filter(state__iexact=state)
            
        district = request.query_params.get('district', None)
        if district:
            # Use vendor's district field, not user's district
            queryset = queryset.filter(district__iexact=district)
            
        city = request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__iexact=city)
            
        pincode = request.query_params.get('pincode', None)
        if pincode:
            queryset = queryset.filter(pincode=pincode)
        
        # Bus count filters - Fixed annotation conflicts
        min_buses = request.query_params.get('min_buses', None)
        max_buses = request.query_params.get('max_buses', None)
        
        if min_buses or max_buses:
            queryset = queryset.annotate(bus_count=Count('bus_set', distinct=True))
            
            if min_buses:
                try:
                    min_buses = int(min_buses)
                    queryset = queryset.filter(bus_count__gte=min_buses)
                except (ValueError, TypeError):
                    pass
                    
            if max_buses:
                try:
                    max_buses = int(max_buses)
                    queryset = queryset.filter(bus_count__lte=max_buses)
                except (ValueError, TypeError):
                    pass
        
        # Package count filters - Fixed field name and annotation conflicts
        min_packages = request.query_params.get('min_packages', None)
        max_packages = request.query_params.get('max_packages', None)
        
        if min_packages or max_packages:
            queryset = queryset.annotate(package_count=Count('package_set', distinct=True))
            
            if min_packages:
                try:
                    min_packages = int(min_packages)
                    queryset = queryset.filter(package_count__gte=min_packages)
                except (ValueError, TypeError):
                    pass
                    
            if max_packages:
                try:
                    max_packages = int(max_packages)
                    queryset = queryset.filter(package_count__lte=max_packages)
                except (ValueError, TypeError):
                    pass
        
        # Filter by vendors with available packages only - Fixed field reference
        has_packages = request.query_params.get('has_packages', None)
        if has_packages and has_packages.lower() == 'true':
            queryset = queryset.filter(package_set__isnull=False).distinct()
            
        # Filter by vendors with buses only
        has_buses = request.query_params.get('has_buses', None)
        if has_buses and has_buses.lower() == 'true':
            queryset = queryset.filter(bus_set__isnull=False).distinct()
        
        # Filter by package availability status - Fixed field reference
        package_status = request.query_params.get('package_status', None)
        if package_status:
            queryset = queryset.filter(package_set__status=package_status).distinct()
        
        # Date range filters (for creation date)
        created_after = request.query_params.get('created_after', None)
        if created_after:
            try:
                date_obj = datetime.strptime(created_after, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_obj)
            except (ValueError, TypeError):
                pass
                
        created_before = request.query_params.get('created_before', None)
        if created_before:
            try:
                date_obj = datetime.strptime(created_before, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_obj)
            except (ValueError, TypeError):
                pass
        
        # Sorting options - Fixed annotation conflicts and field references
        sort_by = request.query_params.get('sort_by', None)
        if sort_by:
            if sort_by == 'name':
                queryset = queryset.order_by('travels_name')
            elif sort_by == 'name_desc':
                queryset = queryset.order_by('-travels_name')
            elif sort_by == 'location':
                queryset = queryset.order_by('city', 'location')
            elif sort_by == 'created_asc':
                queryset = queryset.order_by('created_at')
            elif sort_by == 'bus_count':
                # Check if bus_count annotation already exists
                if not any('bus_count' in str(annotation) for annotation in queryset.query.annotations.keys()):
                    queryset = queryset.annotate(bus_count=Count('bus_set', distinct=True))
                queryset = queryset.order_by('-bus_count')
            elif sort_by == 'package_count':
                # Check if package_count annotation already exists
                if not any('package_count' in str(annotation) for annotation in queryset.query.annotations.keys()):
                    queryset = queryset.annotate(package_count=Count('package_set', distinct=True))
                queryset = queryset.order_by('-package_count')
            # Default sorting by created_at desc is already applied in the initial queryset
        
        return queryset
    
    def get_applied_filters(self, request):
        """Return information about applied filters for debugging/frontend"""
        applied_filters = {}
        
        filter_params = [
            'search', 'state', 'district', 'city', 'pincode',
            'min_buses', 'max_buses', 'min_packages', 'max_packages',
            'has_packages', 'has_buses', 'package_status',
            'created_after', 'created_before', 'sort_by'
        ]
        
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                applied_filters[param] = value
                
        return applied_filters









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

        packages = vendor.package.all()
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
        bus_bookings = list(
            BusBooking.objects.select_related('user')
            .exclude(trip_status='not_started')
        )
        package_bookings = list(
            PackageBooking.objects.select_related('user', 'package')
            .exclude(trip_status='not_started')
        )

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

            bus_bookings = BusBooking.objects.filter(bus__vendor=vendor,trip_status='ongoing')
            package_bookings = PackageBooking.objects.filter(package__vendor=vendor,trip_status='ongoing')

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
        package_bookings = PackageBooking.objects.exclude(trip_status='not_started')
        bus_bookings = BusBooking.objects.exclude(trip_status='not_started')

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
        # Exclude not_started bookings from bus
        bus_booking_counts = (
            BusBooking.objects
            .exclude(trip_status='not_started')
            .values('bus__vendor')
            .annotate(count=Count('id'))
        )
        bus_counts_map = {item['bus__vendor']: item['count'] for item in bus_booking_counts}

        # Exclude not_started bookings from package
        package_booking_counts = (
            PackageBooking.objects
            .exclude(trip_status='not_started')
            .values('package__vendor')
            .annotate(count=Count('id'))
        )
        package_counts_map = {item['package__vendor']: item['count'] for item in package_booking_counts}

        # Merge counts from both
        total_counts = {}
        for vendor_id, count in bus_counts_map.items():
            total_counts[vendor_id] = total_counts.get(vendor_id, 0) + count
        for vendor_id, count in package_counts_map.items():
            total_counts[vendor_id] = total_counts.get(vendor_id, 0) + count

        # Get vendor info
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

            bus_bookings = BusBooking.objects.filter(user=user,trip_status='ongoing')
            package_bookings = PackageBooking.objects.filter(user=user,trip_status='ongoing')

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

        # Exclude 'not_started' from total and today bookings
        total_bus_bookings = BusBooking.objects.exclude(trip_status='not_started').count()
        total_package_bookings = PackageBooking.objects.exclude(trip_status='not_started').count()
        total_bookings = total_bus_bookings + total_package_bookings

        today_bus_bookings = BusBooking.objects.filter(
            created_at__date=today
        ).exclude(trip_status='not_started').count()

        today_package_bookings = PackageBooking.objects.filter(
            created_at__date=today
        ).exclude(trip_status='not_started').count()

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
        bus_bookings = BusBooking.objects.exclude(trip_status='not_started')
        package_bookings = PackageBooking.objects.exclude(trip_status='not_started')

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
        bus_bookings = BusBooking.objects.select_related('bus__vendor').exclude(trip_status='not_started')
        package_bookings = PackageBooking.objects.select_related('package__vendor').exclude(trip_status='not_started')

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
        bus_bookings = BusBooking.objects.exclude(trip_status='not_started')
        package_bookings = PackageBooking.objects.exclude(trip_status='not_started')

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

    def patch(self, request, payout_id):
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
        






class AdminCreateBusAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AdminCreateBusSerializer(data=request.data)
        if serializer.is_valid():
            bus = serializer.save()
            return Response({
                "message": "Bus created successfully for vendor.",
                "data": AdminCreateBusSerializer(bus).data
            }, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    






class AdminEditBusAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, bus_id):
        try:
            bus = Bus.objects.get(pk=bus_id)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminEditBusSerializer(bus, data=request.data, partial=True)
        if serializer.is_valid():
            bus = serializer.save()
            return Response({
                "message": "Bus updated successfully.",
                "data": AdminEditBusSerializer(bus).data
            }, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class BasicPackageAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
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

            serializer = AdminPackageBasicSerializer(data=mutable_data)
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


class AdminEditPackageAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, package_id):
        try:
            package = Package.objects.get(pk=package_id)
        except Package.DoesNotExist:
            return Response({"error": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminEditPackageSerializer(package, data=request.data, partial=True)
        if serializer.is_valid():
            package = serializer.save()
            return Response({
                "message": "Package updated successfully.",
                "data": AdminEditPackageSerializer(package).data
            }, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    




class AdminDeleteBusImageAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, bus_id):
        try:
            bus = Bus.objects.get(pk=bus_id)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = BusImageDeleteSerializer(data=request.data)
        if serializer.is_valid():
            image_ids = serializer.validated_data['image_ids']
            
            # Filter images that belong to this specific bus
            images_to_delete = BusImage.objects.filter(
                bus=bus,
                id__in=image_ids
            )
            
            if not images_to_delete.exists():
                return Response({
                    "error": "No images found for this bus with the provided IDs."
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if deleting these images would leave the bus with no images
            remaining_images = BusImage.objects.filter(bus=bus).exclude(id__in=image_ids)
            if not remaining_images.exists():
                return Response({
                    "error": "Cannot delete all images. At least one image must remain."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            deleted_count = images_to_delete.count()
            images_to_delete.delete()
            
            return Response({
                "message": f"Successfully deleted {deleted_count} image(s).",
                "deleted_image_ids": image_ids
            }, status=status.HTTP_200_OK)
        
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)























import json
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

# Import your models - FIXED: Added missing imports
from vendors.models import ( DayPlan, Place, Stay, Meal, Activity, 
    PlaceImage, StayImage, MealImage, ActivityImage
)
from .serializers import DayPlanSerializer
from vendors.models import Package


class AdminAddDayPlanAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _upload_images(self, files, prefix, related_obj_index, related_obj):
        """Upload images for related objects (Place, Stay, Meal, Activity)"""
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

    def post(self, request, package_id):
        try:
            vendor_id = request.data.get("vendor_id", "")
            
            # Fetch package based on package_id and vendor's user ID
            package = Package.objects.filter(
                id=package_id, 
                vendor__user__id=vendor_id
            ).first()
            
            if not package:
                return Response({"error": "Package not found or access denied"}, status=404)

            data = request.data
            files = request.FILES

            # Get next day number
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
            places_raw = data.get("places", "[]")
            try:
                if isinstance(places_raw, str):
                    places = json.loads(places_raw)
                elif isinstance(places_raw, list):
                    places = places_raw
                else:
                    places = []
            except json.JSONDecodeError as e:
                return Response({"error": f"Invalid JSON in 'places': {str(e)}"}, status=400)

            for idx, place_data in enumerate(places):
                if not isinstance(place_data, dict):
                    return Response({"error": f"Invalid place at index {idx}. Expected object."}, status=400)

                place = Place.objects.create(
                    day_plan=day_plan,
                    name=place_data.get("name", ""),
                    description=place_data.get("description", "")
                )
                self._upload_images(files, "place_image", idx, place)

            # --------- HANDLE STAY (Single Item like Vendor) ---------
            stay_raw = data.get("stay", "[]")
            try:
                if isinstance(stay_raw, str):
                    stay_list = json.loads(stay_raw) if stay_raw.strip() else []
                elif isinstance(stay_raw, list):
                    stay_list = stay_raw
                else:
                    stay_list = []
            except json.JSONDecodeError as e:
                return Response({"error": f"Invalid JSON in 'stay': {str(e)}"}, status=400)

            if stay_list and len(stay_list) > 0:
                stay_data = stay_list[0]  # Take first item like vendor
                if isinstance(stay_data, dict):
                    stay = Stay.objects.create(
                        day_plan=day_plan,
                        hotel_name=stay_data.get("hotel_name", ""),
                        description=stay_data.get("description", ""),
                        location=stay_data.get("location", ""),
                        is_ac=stay_data.get("is_ac", False),
                        has_breakfast=stay_data.get("has_breakfast", False)
                    )
                    self._upload_images(files, "stay_image", 0, stay)

            # --------- HANDLE MEAL (Single Item like Vendor) ---------
            meal_raw = data.get("meal", "[]")
            try:
                if isinstance(meal_raw, str):
                    meal_list = json.loads(meal_raw) if meal_raw.strip() else []
                elif isinstance(meal_raw, list):
                    meal_list = meal_raw
                else:
                    meal_list = []
            except json.JSONDecodeError as e:
                return Response({"error": f"Invalid JSON in 'meal': {str(e)}"}, status=400)

            if meal_list and len(meal_list) > 0:
                meal_data = meal_list[0]  # Take first item like vendor
                if isinstance(meal_data, dict):
                    meal_time = None
                    if meal_data.get("time"):
                        try:
                            meal_time = datetime.strptime(meal_data.get("time"), "%H:%M").time()
                        except ValueError:
                            meal_time = None

                    meal = Meal.objects.create(
                        day_plan=day_plan,
                        type=meal_data.get("type", "breakfast"),
                        description=meal_data.get("description", ""),
                        restaurant_name=meal_data.get("restaurant_name", ""),
                        location=meal_data.get("location", ""),
                        time=meal_time
                    )
                    self._upload_images(files, "meal_image", 0, meal)

            # --------- HANDLE ACTIVITY (Single Item like Vendor) ---------
            activity_raw = data.get("activity", "[]")
            try:
                if isinstance(activity_raw, str):
                    activity_list = json.loads(activity_raw) if activity_raw.strip() else []
                elif isinstance(activity_raw, list):
                    activity_list = activity_raw
                else:
                    activity_list = []
            except json.JSONDecodeError as e:
                return Response({"error": f"Invalid JSON in 'activity': {str(e)}"}, status=400)

            if activity_list and len(activity_list) > 0:
                activity_data = activity_list[0]  # Take first item like vendor
                if isinstance(activity_data, dict):
                    activity_time = None
                    if activity_data.get("time"):
                        try:
                            activity_time = datetime.strptime(activity_data.get("time"), "%H:%M").time()
                        except ValueError:
                            activity_time = None

                    activity = Activity.objects.create(
                        day_plan=day_plan,
                        name=activity_data.get("name", ""),
                        description=activity_data.get("description", ""),
                        location=activity_data.get("location", ""),
                        time=activity_time
                    )
                    self._upload_images(files, "activity_image", 0, activity)

            return Response({
                "message": "Day plan added successfully.",
                "day_plan_id": day_plan.id,
                "day_number": day_plan.day_number
            }, status=201)

        except json.JSONDecodeError as e:
            return Response({"error": f"Invalid JSON: {str(e)}"}, status=400)
        except Exception as e:
            import traceback
            print(f"Error in AdminAddDayPlanAPIView: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
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


class AdminUpdateDayPlanAPIView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _upload_images(self, files, prefix, related_obj_index, related_obj):
        """Upload images for related objects (Place, Stay, Meal, Activity)"""
        for img_index in range(4):  # allow up to 4 images per object
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

    def _delete_existing_images(self, related_obj):
        """Delete existing images for the related object"""
        if isinstance(related_obj, Place):
            images = PlaceImage.objects.filter(place=related_obj)
        elif isinstance(related_obj, Stay):
            images = StayImage.objects.filter(stay=related_obj)
        elif isinstance(related_obj, Meal):
            images = MealImage.objects.filter(meal=related_obj)
        elif isinstance(related_obj, Activity):
            images = ActivityImage.objects.filter(activity=related_obj)
        else:
            return
            
        # Delete image files from storage before deleting records
        for image in images:
            if image.image:
                image.image.delete(save=False)
        images.delete()

    def patch(self, request, package_id, day_number):
        try:
            vendor_id = request.data.get("vendor_id", "")
            
            # FIXED: Correct field lookup
            day_plan = DayPlan.objects.filter(
                package__id=package_id,
                package__vendor__user__id=vendor_id,
                day_number=day_number
            ).first()

            if not day_plan:
                return Response({"error": "Day plan not found"}, status=404)

            data = request.data
            files = request.FILES

            # Update day plan description
            if "description" in data:
                day_plan.description = data.get("description", day_plan.description)
                day_plan.save()

            # Update places
            if "places" in data:
                places_data = data.get("places", "[]")
                if isinstance(places_data, str):
                    places = json.loads(places_data)
                else:
                    places = places_data
                    
                # Delete existing places and their images
                existing_places = Place.objects.filter(day_plan=day_plan)
                for place in existing_places:
                    self._delete_existing_images(place)
                existing_places.delete()
                
                # Create new places
                for idx, place_data in enumerate(places):
                    place = Place.objects.create(
                        day_plan=day_plan,
                        name=place_data.get("name", ""),
                        description=place_data.get("description", "")
                    )
                    self._upload_images(files, "place_image", idx, place)

            # Update stay - FIXED: Handle OneToOneField correctly
            if "stay" in data:
                stay_data_raw = data.get("stay", "{}")
                if isinstance(stay_data_raw, str):
                    stay_data = json.loads(stay_data_raw) if stay_data_raw != "{}" else {}
                else:
                    stay_data = stay_data_raw
                    
                # Delete existing stay and images
                try:
                    existing_stay = day_plan.stay  # OneToOneField access
                    self._delete_existing_images(existing_stay)
                    existing_stay.delete()
                except Stay.DoesNotExist:
                    pass  # No existing stay
                
                # Create new stay
                if stay_data:  # Only create if data provided
                    stay = Stay.objects.create(
                        day_plan=day_plan,
                        hotel_name=stay_data.get("hotel_name", ""),
                        description=stay_data.get("description", ""),
                        location=stay_data.get("location", ""),
                        is_ac=stay_data.get("is_ac", False),
                        has_breakfast=stay_data.get("has_breakfast", False)
                    )
                    self._upload_images(files, "stay_image", 0, stay)

            # Update meals
            if "meal" in data:
                meal_data_raw = data.get("meal", "[]")
                if isinstance(meal_data_raw, str):
                    meal_list = json.loads(meal_data_raw)
                else:
                    meal_list = meal_data_raw
                    
                # Delete existing meals and images
                existing_meals = Meal.objects.filter(day_plan=day_plan)
                for meal in existing_meals:
                    self._delete_existing_images(meal)
                existing_meals.delete()
                
                # Create new meals
                for idx, meal_data in enumerate(meal_list):
                    meal_time = None
                    if meal_data.get("time"):
                        try:
                            meal_time = datetime.strptime(meal_data.get("time"), "%H:%M").time()
                        except ValueError:
                            meal_time = None
                            
                    meal = Meal.objects.create(
                        day_plan=day_plan,
                        type=meal_data.get("type", "breakfast"),
                        description=meal_data.get("description", ""),
                        restaurant_name=meal_data.get("restaurant_name", ""),
                        location=meal_data.get("location", ""),
                        time=meal_time
                    )
                    self._upload_images(files, "meal_image", idx, meal)

            # Update activities
            if "activity" in data:
                activity_data_raw = data.get("activity", "[]")
                if isinstance(activity_data_raw, str):
                    activity_list = json.loads(activity_data_raw)
                else:
                    activity_list = activity_data_raw
                    
                # Delete existing activities and images
                existing_activities = Activity.objects.filter(day_plan=day_plan)
                for activity in existing_activities:
                    self._delete_existing_images(activity)
                existing_activities.delete()
                
                # Create new activities
                for idx, activity_data in enumerate(activity_list):
                    activity_time = None
                    if activity_data.get("time"):
                        try:
                            activity_time = datetime.strptime(activity_data.get("time"), "%H:%M").time()
                        except ValueError:
                            activity_time = None
                            
                    activity = Activity.objects.create(
                        day_plan=day_plan,
                        name=activity_data.get("name", ""),
                        description=activity_data.get("description", ""),
                        location=activity_data.get("location", ""),
                        time=activity_time
                    )
                    self._upload_images(files, "activity_image", idx, activity)

            return Response({"message": "Day plan updated successfully."}, status=200)

        except json.JSONDecodeError as e:
            return Response({"error": f"Invalid JSON data: {str(e)}"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# NEW: Day Plan Delete API View
class AdminDayPlanDeleteAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _delete_all_images(self, day_plan):
        """Delete all images associated with a day plan"""
        # Delete place images
        places = Place.objects.filter(day_plan=day_plan)
        for place in places:
            place_images = PlaceImage.objects.filter(place=place)
            for img in place_images:
                if img.image:
                    img.image.delete(save=False)
            place_images.delete()

        # Delete stay images
        try:
            stay = day_plan.stay
            stay_images = StayImage.objects.filter(stay=stay)
            for img in stay_images:
                if img.image:
                    img.image.delete(save=False)
            stay_images.delete()
        except Stay.DoesNotExist:
            pass

        # Delete meal images
        meals = Meal.objects.filter(day_plan=day_plan)
        for meal in meals:
            meal_images = MealImage.objects.filter(meal=meal)
            for img in meal_images:
                if img.image:
                    img.image.delete(save=False)
            meal_images.delete()

        # Delete activity images
        activities = Activity.objects.filter(day_plan=day_plan)
        for activity in activities:
            activity_images = ActivityImage.objects.filter(activity=activity)
            for img in activity_images:
                if img.image:
                    img.image.delete(save=False)
            activity_images.delete()

    def delete(self, request, package_id, day_number):
        try:
            # Get day plan with proper authentication check
            day_plan = DayPlan.objects.filter(
                package__id=package_id,
                package__vendor__user=request.user,
                day_number=day_number
            ).first()

            if not day_plan:
                return Response({"error": "Day plan not found"}, status=404)

            # Delete all associated images first
            self._delete_all_images(day_plan)

            # Delete the day plan (this will cascade delete all related objects)
            day_plan.delete()

            return Response({"message": "Day plan deleted successfully"}, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


# FIXED: Image Management API View
class ImageManagementAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, image_type, image_id):
        """Delete a specific image"""
        try:
            vendor_id = request.data.get("vendor_id")
            # FIXED: Correct field lookups for all image types
            if image_type == 'place':
                image = PlaceImage.objects.get(
                    id=image_id, 
                    place__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'stay':
                image = StayImage.objects.get(
                    id=image_id, 
                    stay__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'meal':
                image = MealImage.objects.get(
                    id=image_id, 
                    meal__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'activity':
                image = ActivityImage.objects.get(
                    id=image_id, 
                    activity__day_plan__package__vendor__user=vendor_id
                )
            else:
                return Response({"error": "Invalid image type"}, status=400)
            
            # Delete the file from storage
            if image.image:
                image.image.delete(save=False)
            image.delete()
            
            return Response({"message": "Image deleted successfully"}, status=200)
            
        except (PlaceImage.DoesNotExist, StayImage.DoesNotExist, 
                MealImage.DoesNotExist, ActivityImage.DoesNotExist):
            return Response({"error": "Image not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def patch(self, request, image_type, image_id):
        """Edit/Replace an existing image"""
        try:
            # Get the new image file
            new_image = request.FILES.get('image')
            vendor_id = request.data.get("vendor_id")
            if not new_image:
                return Response({"error": "No image file provided"}, status=400)
            
            # FIXED: Correct field lookups
            if image_type == 'place':
                image = PlaceImage.objects.get(
                    id=image_id, 
                    place__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'stay':
                image = StayImage.objects.get(
                    id=image_id, 
                    stay__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'meal':
                image = MealImage.objects.get(
                    id=image_id, 
                    meal__day_plan__package__vendor__user=vendor_id
                )
            elif image_type == 'activity':
                image = ActivityImage.objects.get(
                    id=image_id, 
                    activity__day_plan__package__vendor__user=vendor_id
                )
            else:
                return Response({"error": "Invalid image type"}, status=400)
            
            # Delete old image file from storage
            if image.image:
                image.image.delete(save=False)
            
            # Update with new image
            image.image = new_image
            image.save()
            
            return Response({
                "message": "Image updated successfully",
                "image": {
                    "id": image.id,
                    "url": image.image.url if image.image else None
                }
            }, status=200)
            
        except (PlaceImage.DoesNotExist, StayImage.DoesNotExist, 
                MealImage.DoesNotExist, ActivityImage.DoesNotExist):
            return Response({"error": "Image not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request, image_type, object_id):
        """Add new images to existing objects"""
        try:
            files = request.FILES
            vendor_id = request.data.get("vendor_id")
            
            # FIXED: Correct field lookups and object retrieval
            if image_type == 'place':
                obj = Place.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=vendor_id
                )
                ImageModel = PlaceImage
                field_name = 'place'
            elif image_type == 'stay':
                obj = Stay.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=vendor_id
                )
                ImageModel = StayImage
                field_name = 'stay'
            elif image_type == 'meal':
                obj = Meal.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=vendor_id
                )
                ImageModel = MealImage
                field_name = 'meal'
            elif image_type == 'activity':
                obj = Activity.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=vendor_id
                )
                ImageModel = ActivityImage
                field_name = 'activity'
            else:
                return Response({"error": "Invalid image type"}, status=400)
            
            # Check current image count
            current_count = ImageModel.objects.filter(**{field_name: obj}).count()
            max_images = 4
            
            if current_count >= max_images:
                return Response({"error": f"Maximum {max_images} images allowed"}, status=400)
            
            created_images = []
            for key, image_file in files.items():
                if current_count < max_images:
                    image_obj = ImageModel.objects.create(**{field_name: obj, 'image': image_file})
                    created_images.append({
                        'id': image_obj.id,
                        'url': image_obj.image.url if image_obj.image else None
                    })
                    current_count += 1
            
            return Response({
                "message": f"{len(created_images)} images added successfully",
                "images": created_images
            }, status=201)
            
        except (Place.DoesNotExist, Stay.DoesNotExist, 
                Meal.DoesNotExist, Activity.DoesNotExist):
            return Response({"error": "Object not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# FIXED: Bulk Image Management View
class BulkImageManagementAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, image_type, object_id):
        """Replace all images for an object at once"""
        try:
            files = request.FILES
            
            # FIXED: Correct field lookups
            if image_type == 'place':
                obj = Place.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = PlaceImage
                field_name = 'place'
            elif image_type == 'stay':
                obj = Stay.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = StayImage
                field_name = 'stay'
            elif image_type == 'meal':
                obj = Meal.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = MealImage
                field_name = 'meal'
            elif image_type == 'activity':
                obj = Activity.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = ActivityImage
                field_name = 'activity'
            else:
                return Response({"error": "Invalid image type"}, status=400)
            
            # Delete all existing images
            existing_images = ImageModel.objects.filter(**{field_name: obj})
            for img in existing_images:
                if img.image:
                    img.image.delete(save=False)
            existing_images.delete()
            
            # Add new images
            created_images = []
            max_images = 4
            
            for i, (key, image_file) in enumerate(files.items()):
                if i < max_images:
                    image_obj = ImageModel.objects.create(**{field_name: obj, 'image': image_file})
                    created_images.append({
                        'id': image_obj.id,
                        'url': image_obj.image.url if image_obj.image else None
                    })
            
            return Response({
                "message": f"All images replaced successfully. {len(created_images)} images added.",
                "images": created_images
            }, status=200)
            
        except (Place.DoesNotExist, Stay.DoesNotExist, 
                Meal.DoesNotExist, Activity.DoesNotExist):
            return Response({"error": "Object not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request, image_type, object_id):
        """Reorder images by providing new order"""
        try:
            # Expecting JSON with image IDs in desired order
            image_ids = request.data.get('image_order', [])
            
            # FIXED: Correct field lookups
            if image_type == 'place':
                obj = Place.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = PlaceImage
                field_name = 'place'
            elif image_type == 'stay':
                obj = Stay.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = StayImage
                field_name = 'stay'
            elif image_type == 'meal':
                obj = Meal.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = MealImage
                field_name = 'meal'
            elif image_type == 'activity':
                obj = Activity.objects.get(
                    id=object_id, 
                    day_plan__package__vendor__user=request.user
                )
                ImageModel = ActivityImage
                field_name = 'activity'
            else:
                return Response({"error": "Invalid image type"}, status=400)
            
            # Update image order (assuming you have an order field in your model)
            for index, image_id in enumerate(image_ids):
                try:
                    image = ImageModel.objects.get(id=image_id, **{field_name: obj})
                    # If you have an order field, update it
                    if hasattr(image, 'order'):
                        image.order = index
                        image.save()
                except ImageModel.DoesNotExist:
                    continue
            
            return Response({"message": "Images reordered successfully"}, status=200)
            
        except (Place.DoesNotExist, Stay.DoesNotExist, 
                Meal.DoesNotExist, Activity.DoesNotExist):
            return Response({"error": "Object not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)