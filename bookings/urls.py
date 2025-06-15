from django.urls import path
from .views import (
    PackageListAPIView, BusListAPIView,
    PackageBookingListCreateAPIView, PackageBookingDetailAPIView,
    BusBookingListCreateAPIView, BusBookingDetailAPIView,
    TravelerCreateAPIView, PackageBookingTravelersAPIView, BusBookingTravelersAPIView,
    TravelerDetailAPIView, UserBookingsByStatus,CancelBookingView,PackageCategoryListAPIView,PackageSubCategoryListAPIView,
    SingleBusListAPIView,SinglePackageListAPIView,
    PopularBusApi,PackageBookingUpdateAPIView,PackageDriverDetailListAPIView,UserBusSearchCreateAPIView,
    FooterSectionListAPIView,AdvertisementListAPIView,PilgrimagePackagesAPIView,BusBookingUpdateAPIView,
    ApplyWalletToBusBookingAPIView,
    RemoveWalletFromBusBookingAPIView,
    ApplyWalletToPackageBookingAPIView,
    RemoveWalletFromPackageBookingAPIView,
    GetWalletBalanceAPIView,
    WalletTransactionHistoryAPIView,BusDriverDetailListAPIView

)

urlpatterns = [
    # Vendor resource endpoints
    path('packages/<int:category>/', PackageListAPIView.as_view(), name='package-list'),
    path('buses/', BusListAPIView.as_view(), name='bus-list'),

    path('bus/details/<int:bus_id>/',SingleBusListAPIView.as_view(),name="bus detail"),
    path('package/details/<int:package_id>/',SinglePackageListAPIView.as_view(),name="bus_details"),
    
    # Package booking endpoints
    path('bookings/package/', PackageBookingListCreateAPIView.as_view(), name='package-booking-list-create'),
    path('bookings/package/<int:pk>/', PackageBookingDetailAPIView.as_view(), name='package-booking-detail'),
    path('bookings/package/<int:booking_id>/travelers/', PackageBookingTravelersAPIView.as_view(), name='package-booking-travelers'),
    path('bookings/package/<int:booking_id>/edit/', PackageBookingUpdateAPIView.as_view(), name='package-booking-update'),
    
    # Bus ing endpoints
    path('bookings/bus/', BusBookingListCreateAPIView.as_view(), name='bus-booking-list-create'),
    path('bookings/bus/<int:pk>/', BusBookingDetailAPIView.as_view(), name='bus-booking-detail'),
    path('bookings/bus/<int:booking_id>/travelers/', BusBookingTravelersAPIView.as_view(), name='bus-booking-travelers'),
    path('bookings/bus/<int:booking_id>/edit/', BusBookingUpdateAPIView.as_view(), name='bus-booking-update'),

    path('bookings/cancel/',CancelBookingView.as_view(),name="booking_cancel"),
    
    # Bookstatus endpoints
    path('bookings/status/<str:status_filter>/', UserBookingsByStatus.as_view(), name='bookings-by-status'),
    
    # Trav endpoints
    path('travelers/create/', TravelerCreateAPIView.as_view(), name='traveler-create'),
    path('travelers/<int:pk>/', TravelerDetailAPIView.as_view(), name='traveler-detail'),

    path('services/categories/', PackageCategoryListAPIView.as_view(), name='package-category-list'),
    path('services/subcategories/<int:category>/', PackageSubCategoryListAPIView.as_view(), name='package-subcategory-list'),

    path('popular-buses/',PopularBusApi.as_view(),name="Popular-buses"),

    path('package-drivers/<int:booking_id>/', PackageDriverDetailListAPIView.as_view(), name='package-drivers'),
    path('bus-drivers/<int:booking_id>/', BusDriverDetailListAPIView.as_view(), name='Bus-drivers'),

    path('footer-sections/', FooterSectionListAPIView.as_view(), name='footer-section-list'),

    path('advertisements/', AdvertisementListAPIView.as_view(), name='advertisement-list'),

    path('bus-search/',UserBusSearchCreateAPIView.as_view(),name="bus-search"),

    path('pilgrimage/', PilgrimagePackagesAPIView.as_view(), name='pilgrimage-packages'),


    # Wallet balance endpoint
    path('wallet/balance/', GetWalletBalanceAPIView.as_view(), name='wallet-balance'),
    
    # Bus booking wallet operations
    path('wallet/bus-booking/<str:booking_id>/apply/', ApplyWalletToBusBookingAPIView.as_view(), name='apply-wallet-bus-booking'),
    path('wallet/bus-booking/<str:booking_id>/remove/', RemoveWalletFromBusBookingAPIView.as_view(), name='remove-wallet-bus-booking'),
    
    # Package booking wallet operations
    path('wallet/package-booking/<str:booking_id>/apply/', ApplyWalletToPackageBookingAPIView.as_view(), name='apply-wallet-package-booking'),
    path('wallet/package-booking/<str:booking_id>/remove/', RemoveWalletFromPackageBookingAPIView.as_view(), name='remove-wallet-package-booking'),

    path('wallet/transactions/',WalletTransactionHistoryAPIView.as_view(), name='wallet-transactions'),

]