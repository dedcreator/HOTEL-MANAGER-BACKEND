# backend/accounts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from . import views

router = DefaultRouter()
router.register('staff', views.StaffViewSet, basename='staff')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('me/', views.me, name='me'),
    path('register/', views.register, name='register'),
    
    # Password Reset URLs
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('verify-reset-token/', views.verify_reset_token, name='verify-reset-token'),
    path('reset-password/', views.reset_password, name='reset-password'),
    
    # Profile URLs
    path('update-profile/', views.update_profile, name='update-profile'),
    path('change-password/', views.change_password, name='change-password'),
    
    # JWT Token URLs - MAKE SURE THESE EXIST
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
]