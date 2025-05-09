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

    # def get(self, request, user_id=None):
    #     if user_id:
    #         try:
    #             user = User.objects.get(id=user_id, role=User.USER)
    #             serializer = UserSerializer(user)
    #             return Response(serializer.data, status=status.HTTP_200_OK)
    #         except User.DoesNotExist:
    #             return Response({"error": "User not found or not a normal user."}, status=status.HTTP_404_NOT_FOUND)
    #     else:
    #         users = User.objects.filter(role=User.USER)
    #         serializer = UserSerializer(users, many=True)
    #         return Response({
    #             "total_users": users.count(),
    #             "users": serializer.data
    #         }, status=status.HTTP_200_OK)

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
class AllSectionsCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

 

    # def post(self, request, *args, **kwargs):
       
        
    #     try:
    #         ads_data = []
    #         for i in range(len(request.data.getlist('advertisements-0-title'))):
    #             ad = {
    #                 'title': request.data.getlist(f'advertisements-{i}-title')[0],
    #                 'description': request.data.getlist(f'advertisements-{i}-description')[0],
    #                 'image': request.FILES.get(f'advertisements-{i}-image') if f'advertisements-{i}-image' in request.FILES else None
    #             }
    #             ads_data.append(ad)

    #         deals_data = []
    #         for i in range(len(request.data.getlist('limited_deals-0-title'))):
    #             deal = {
    #                 'title': request.data.getlist(f'limited_deals-{i}-title')[0],
    #                 'description': request.data.getlist(f'limited_deals-{i}-description')[0],
    #                 'images': request.FILES.getlist(f'limited_deals-{i}-images') if f'limited_deals-{i}-images' in request.FILES else []
    #             }
    #             deals_data.append(deal)

    #         footers_data = []
    #         for i in range(len(request.data.getlist('footer_sections-0-title'))):
    #             footer = {
    #                 'title': request.data.getlist(f'footer_sections-{i}-title')[0],
    #                 'description': request.data.getlist(f'footer_sections-{i}-description')[0],
    #                 'image': request.FILES.get(f'footer_sections-{i}-image') if f'footer_sections-{i}-image' in request.FILES else None
    #             }
    #             footers_data.append(footer)

          
            
    #     except Exception as e:
    #         print(f"Error: {str(e)}")
    #         return Response({"error": "Invalid data format."}, status=400)

    #     for ad in ads_data:
    #         print(f"Processing Advertisement: {ad}")
    #         serializer = AdvertisementSerializer(data=ad)
    #         if serializer.is_valid():
    #             serializer.save()
    #         else:
    #             print(f"Advertisement serializer errors: {serializer.errors}")
    #             return Response({'error': serializer.errors}, status=400)

    #     for deal in deals_data:
    #         print(f"Processing Limited Deal: {deal}")
    #         images = deal.pop('images', [])
    #         deal_serializer = LimitedDealSerializer(data=deal)
    #         if deal_serializer.is_valid():
    #             limited_deal = deal_serializer.save()
    #             for img in images:
    #                 print(f"Processing image for deal: {img}")
    #                 LimitedDealImage.objects.create(deal=limited_deal, image=img)
    #         else:
    #             print(f"Limited Deal serializer errors: {deal_serializer.errors}")
    #             return Response({'error': deal_serializer.errors}, status=400)

    #     for footer in footers_data:
    #         print(f"Processing Footer Section: {footer}")
    #         footer_serializer = FooterSectionSerializer(data=footer)
    #         if footer_serializer.is_valid():
    #             footer_serializer.save()
    #         else:
    #             print(f"Footer Section serializer errors: {footer_serializer.errors}")
    #             return Response({'error': footer_serializer.errors}, status=400)

    #     print("All data saved successfully!")
    #     return Response({"message": "All data saved successfully!"}, status=201)





    def post(self, request, *args, **kwargs):
        try:
            # 1. Parse advertisements
            ads_data = []
            i = 0
            while f'advertisements-{i}-title' in request.data:
                ad = {
                    'title': request.data.get(f'advertisements-{i}-title'),
                    'description': request.data.get(f'advertisements-{i}-description'),
                    'image': request.FILES.get(f'advertisements-{i}-image')
                }
                ads_data.append(ad)
                i += 1

            ad_instances = []
            for ad in ads_data:
                serializer = AdvertisementSerializer(data=ad)
                if serializer.is_valid():
                    instance = serializer.save()
                    ad_instances.append(instance)
                else:
                    return Response({'error': serializer.errors}, status=400)

            # 2. Parse limited deals (each linked to an ad)
            deals_data = []
            i = 0
            while f'limited_deals-{i}-title' in request.data:
                deal = {
                    'title': request.data.get(f'limited_deals-{i}-title'),
                    'description': request.data.get(f'limited_deals-{i}-description'),
                    'images': request.FILES.getlist(f'limited_deals-{i}-images'),
                    'advertisement': ad_instances[i] if i < len(ad_instances) else None
                }
                deals_data.append(deal)
                i += 1

            deal_instances = []
            for deal in deals_data:
                images = deal.pop('images', [])
                ad_obj = deal.pop('advertisement')
                deal_serializer = LimitedDealSerializer(data=deal)
                if deal_serializer.is_valid():
                    limited_deal = deal_serializer.save(advertisement=ad_obj)
                    deal_instances.append(limited_deal)
                    for img in images:
                        LimitedDealImage.objects.create(deal=limited_deal, image=img)
                else:
                    return Response({'error': deal_serializer.errors}, status=400)

            # 3. Parse footer sections (each linked to an ad)
            footers_data = []
            i = 0
            while f'footer_sections-{i}-title' in request.data:
                footer = {
                    'title': request.data.get(f'footer_sections-{i}-title'),
                    'description': request.data.get(f'footer_sections-{i}-description'),
                    'image': request.FILES.get(f'footer_sections-{i}-image'),
                    'advertisement': ad_instances[i] if i < len(ad_instances) else None
                }
                footers_data.append(footer)
                i += 1

            for footer in footers_data:
                ad_obj = footer.pop('advertisement')
                footer_serializer = FooterSectionSerializer(data=footer)
                if footer_serializer.is_valid():
                    footer_serializer.save(advertisement=ad_obj)
                else:
                    return Response({'error': footer_serializer.errors}, status=400)

            return Response({"message": "All data saved successfully!"}, status=201)

        except Exception as e:
            print(f"Error: {str(e)}")
            return Response({"error": str(e)}, status=400)





    # def get(self, request, *args, **kwargs):
    #     ads = Advertisement.objects.all()
    #     deals = LimitedDeal.objects.all()
    #     footers = FooterSection.objects.all()

    #     ads_serialized = AdvertisementSerializer(ads, many=True).data
    #     deals_serialized = LimitedDealSerializer(deals, many=True).data
    #     footers_serialized = FooterSectionSerializer(footers, many=True).data

    #     return Response({
    #         "advertisements": ads_serialized,
    #         "limited_deals": deals_serialized,
    #         "footer_sections": footers_serialized
    #     }, status=200)


    def get(self, request, *args, **kwargs):
        ads = Advertisement.objects.all()
        ads_serialized = AdvertisementSerializer(ads, many=True).data

        return Response({
            "advertisements": ads_serialized
        }, status=200)



class AdvertisementDetailView(APIView):
   
    def get(self, request, ad_id, *args, **kwargs):
        try:
            advertisement = Advertisement.objects.get(id=ad_id)
            print(advertisement, 'avd')  
        except Advertisement.DoesNotExist:
            return Response({"error": "Advertisement not found."}, status=status.HTTP_404_NOT_FOUND)
        
        ad_data = AdvertisementSerializer(advertisement).data
        print(ad_data, 'ad_data')   

        deals = LimitedDeal.objects.filter(advertisement=advertisement)
        print(deals, 'dela')   

        deals_data = LimitedDealSerializer(deals, many=True).data
        print(deals_data, 'deals data')   

        footers = FooterSection.objects.filter(advertisement=advertisement)
        print(footers, 'footers')   

        footers_data = FooterSectionSerializer(footers, many=True).data
        print(footers_data, 'footers data')  

        return Response({
            "advertisement": ad_data,
            "limited_deals": deals_data,
            "footer_sections": footers_data
        }, status=status.HTTP_200_OK)



#EXPLROE CREATING
class ExploreSectionCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        data = request.data

        sight_data = {
            'title': data.get('sight[title]'),
            'description': data.get('sight[description]'),
            'season_description': data.get('sight[season_description]'),
            'image': data.get('sight[image]')
        }

        experience_data = []
        index = 0
        while f'experiences[{index}][description]' in data:
            exp = {
                'description': data.get(f'experiences[{index}][description]'),
                'image': data.get(f'experiences[{index}][image]')
            }
            experience_data.append(exp)
            index += 1

        sight_serializer = SightSerializer(data=sight_data)
        if sight_serializer.is_valid():
            sight_instance = sight_serializer.save()

            for exp in experience_data:
                exp_serializer = ExperienceSerializer(data=exp)
                if exp_serializer.is_valid():
                    exp_serializer.save(sight=sight_instance)
                else:
                    return Response({"error": exp_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Sight and experiences created successfully!"}, status=status.HTTP_201_CREATED)

        return Response({"error": sight_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)




    def patch(self, request, *args, **kwargs):
        print('is working')
        sight_id = kwargs.get('pk')   
        try:
            sight_instance = Sight.objects.get(pk=sight_id)
        except Sight.DoesNotExist:
            return Response({"error": "Sight not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        sight_data = {
            'title': data.get('sight[title]'),
            'description': data.get('sight[description]'),
            'season_description': data.get('sight[season_description]'),
            'image': data.get('sight[image]')
        }
        sight_data = {key: value for key, value in sight_data.items() if value is not None}

        sight_serializer = SightSerializer(sight_instance, data=sight_data, partial=True)
        if sight_serializer.is_valid():
            sight_serializer.save()
        else:
            return Response({"error": sight_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        experience_data = []
        index = 0
        while f'experiences[{index}][description]' in data:
            exp = {
                'description': data.get(f'experiences[{index}][description]'),
                'image': data.get(f'experiences[{index}][image]')
            }
            experience_data.append(exp)
            index += 1

        if experience_data:
            

            for exp in experience_data:
                exp_serializer = ExperienceSerializer(data=exp)
                if exp_serializer.is_valid():
                    exp_serializer.save(sight=sight_instance)
                else:
                    return Response({"error": exp_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Sight updated successfully."}, status=status.HTTP_200_OK)



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
        vendors = Vendor.objects.all()
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
        serializer = BusAdminSerializer(buses, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)





class SingleBusDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, bus_id):
        try:
            bus = Bus.objects.get(id=bus_id)
        except Bus.DoesNotExist:
            return Response({'detail': 'Bus not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BusDetailSerializerADMIN(bus, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)




class AdminPackageListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        if not sub_category_id:
            return Response({"detail": "Sub category ID is required."}, status=400)

        packages = Package.objects.filter(sub_category_id=sub_category_id).prefetch_related('buses__features', 'buses__vendor')
        serializer = PackageListSerializer(packages, many=True)
        return Response(serializer.data)





class AdminPackageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            package = Package.objects.get(pk=pk)
        except Package.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackageDetailSerializer(package, context={'request': request})
        return Response(serializer.data)







