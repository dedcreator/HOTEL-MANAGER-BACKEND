# backend/inventory/serializers.py

from rest_framework import serializers
from .models import Product, Batch, StockMovement, StockAlert

class ProductSerializer(serializers.ModelSerializer):
    total_stock = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    can_delete = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return request.user.role == 'ceo'
        return False
    
    def validate_name(self, value):
        if self.instance:
            if Product.objects.filter(name__iexact=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("A product with this name already exists")
        else:
            if Product.objects.filter(name__iexact=value).exists():
                raise serializers.ValidationError("A product with this name already exists")
        return value


class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.username', read_only=True)
    received_by_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = '__all__'
        read_only_fields = ['date_received']
    
    def get_received_by_full_name(self, obj):
        if obj.received_by:
            return f"{obj.received_by.get_full_name() or obj.received_by.username}"
        return "System"


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    created_by_full_name = serializers.SerializerMethodField()
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'batch', 'quantity', 
            'movement_type', 'movement_type_display', 'price_at_movement',
            'notes', 'created_at', 'created_by', 'created_by_name', 'created_by_full_name'
        ]
    
    def get_created_by_full_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.get_full_name() or obj.created_by.username}"
        return "System"

class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = '__all__'


class SimpleProductSerializer(serializers.ModelSerializer):
    """Simplified product serializer for dropdowns"""
    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'default_price', 'total_stock', 'is_low_stock', 'location', 'is_premium']


class AddStockSerializer(serializers.Serializer):
    """Serializer for adding stock to a product"""
    quantity = serializers.IntegerField(min_value=1)
    cost_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    supplier = serializers.CharField(required=False, allow_blank=True)
    batch_number = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)