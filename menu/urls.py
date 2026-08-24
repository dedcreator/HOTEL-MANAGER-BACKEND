# backend/menu/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    MenuItemViewSet,
    DiningTableViewSet,
    MenuOrderViewSet,
    public_categories,
    public_items,
    public_tables,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='menu-categories')
router.register('items', MenuItemViewSet, basename='menu-items')
router.register('tables', DiningTableViewSet, basename='menu-tables')
router.register('orders', MenuOrderViewSet, basename='menu-orders')

urlpatterns = [
    # Public endpoints
    path('public/categories/', public_categories, name='menu-public-categories'),
    path('public/items/', public_items, name='menu-public-items'),
    path('public/tables/', public_tables, name='menu-public-tables'),
    
    # Viewset endpoints
    path('', include(router.urls)),
]
