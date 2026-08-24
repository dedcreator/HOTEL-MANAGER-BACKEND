# backend/menu/admin.py
from django.contrib import admin
from .models import Category, MenuItem, DiningTable, MenuOrder, MenuOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'is_active', 'sort_order', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available', 'is_popular', 'is_new', 'preparation_time']
    list_filter = ['category', 'is_available', 'is_popular', 'is_new']
    search_fields = ['name', 'description']
    list_editable = ['price', 'is_available']


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ['table_number', 'name', 'slug', 'capacity', 'status', 'section', 'is_active']
    list_filter = ['status', 'section', 'is_active']
    search_fields = ['table_number', 'name', 'slug']


class MenuOrderItemInline(admin.TabularInline):
    model = MenuOrderItem
    extra = 0
    readonly_fields = ['subtotal']


@admin.register(MenuOrder)
class MenuOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'table', 'customer_name', 'total_amount', 'status', 'payment_status', 'payment_method', 'placed_at']
    list_filter = ['status', 'payment_status', 'payment_method', 'placed_at']
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    inlines = [MenuOrderItemInline]
