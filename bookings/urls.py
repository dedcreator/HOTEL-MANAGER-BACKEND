# backend/bookings/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import public_views

router = DefaultRouter()
router.register('guests', views.GuestViewSet, basename='guest')
router.register('', views.BookingViewSet, basename='booking')

urlpatterns = [
    # Public endpoints (no auth required) - MUST come before router
    path('public/test/', public_views.test, name='public-test'),
    path('public/availability/', public_views.check_availability, name='public-availability'),
    path('public/create/', public_views.create_booking, name='public-create-explicit'),
    path('public/', public_views.create_booking, name='public-create'),
    
    # Protected endpoints (require authentication)
    path('', include(router.urls)),
]