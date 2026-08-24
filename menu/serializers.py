# backend/menu/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import Category, MenuItem, DiningTable, MenuOrder, MenuOrderItem


class CategorySerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 
            'is_active', 'sort_order', 'item_count',
            'created_at', 'updated_at'
        ]


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'category',
            'category_name', 'is_available', 'is_popular', 'is_new',
            'is_vegetarian', 'is_gluten_free', 'is_vegan',
            'preparation_time', 'image', 'icon_name',
            'dietary_tags', 'sort_order', 'created_at', 'updated_at'
        ]


class DiningTableSerializer(serializers.ModelSerializer):
    menu_url = serializers.CharField(read_only=True)

    class Meta:
        model = DiningTable
        fields = [
            'id', 'table_number', 'name', 'slug', 'capacity',
            'status', 'is_active', 'section', 'floor',
            'qr_code', 'qr_code_url', 'menu_url',
            'created_at', 'updated_at'
        ]


class MenuOrderItemSerializer(serializers.ModelSerializer):
    menu_item_id = serializers.UUIDField(source='menu_item.id', read_only=True)

    class Meta:
        model = MenuOrderItem
        fields = [
            'id', 'menu_item', 'menu_item_id', 'item_name',
            'quantity', 'unit_price', 'subtotal',
            'special_instructions'
        ]


class MenuOrderSerializer(serializers.ModelSerializer):
    items = MenuOrderItemSerializer(many=True, read_only=True)
    table_number = serializers.CharField(read_only=True)
    table_name = serializers.CharField(source='table.name', read_only=True, default='')

    class Meta:
        model = MenuOrder
        fields = [
            'id', 'order_number', 'table', 'table_number', 'table_name',
            'customer_name', 'customer_email', 'customer_phone',
            'subtotal', 'tax', 'discount', 'total_amount',
            'status', 'payment_status', 'payment_method',
            'notes', 'special_instructions', 'staff',
            'items', 'placed_at', 'updated_at'
        ]


class CreateOrderItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')


class CreateMenuOrderSerializer(serializers.Serializer):
    table = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    customer_name = serializers.CharField(required=False, default='Guest')
    customer_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')
    items = CreateOrderItemInputSerializer(many=True)

    def create(self, validated_data):
        import uuid
        items_data = validated_data.pop('items')
        table_identifier = validated_data.pop('table', None)

        dining_table = None
        if table_identifier:
            table_str = str(table_identifier).strip()
            try:
                uuid_obj = uuid.UUID(table_str)
                dining_table = DiningTable.objects.filter(id=uuid_obj).first()
            except (ValueError, AttributeError, TypeError):
                dining_table = None

            if not dining_table:
                dining_table = DiningTable.objects.filter(slug=table_str).first()
            if not dining_table:
                dining_table = DiningTable.objects.filter(table_number=table_str).first()

        order = MenuOrder.objects.create(
            table=dining_table,
            customer_name=validated_data.get('customer_name') or (f"Table {dining_table.table_number}" if dining_table else 'Guest'),
            customer_email=validated_data.get('customer_email') or None,
            customer_phone=validated_data.get('customer_phone') or None,
            notes=validated_data.get('notes', ''),
            special_instructions=validated_data.get('special_instructions', ''),
            status='pending',
            payment_status='pending',
        )

        subtotal = Decimal('0.00')
        for item_data in items_data:
            item_id = str(item_data['menu_item_id']).strip()
            qty = item_data.get('quantity', 1)
            instructions = item_data.get('special_instructions', '')

            menu_item = None
            try:
                item_uuid = uuid.UUID(item_id)
                menu_item = MenuItem.objects.filter(id=item_uuid).first()
            except (ValueError, AttributeError, TypeError):
                menu_item = None

            if not menu_item:
                menu_item = MenuItem.objects.filter(name__iexact=item_id).first()

            if not menu_item:
                continue

            unit_price = menu_item.price
            item_name = menu_item.name

            item_subtotal = (Decimal(str(qty)) * unit_price).quantize(Decimal('0.01'))
            subtotal += item_subtotal

            MenuOrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                item_name=item_name,
                quantity=qty,
                unit_price=unit_price,
                subtotal=item_subtotal,
                special_instructions=instructions
            )

        order.subtotal = subtotal
        order.tax = (subtotal * Decimal('0.075')).quantize(Decimal('0.01'))
        order.total_amount = (subtotal + order.tax).quantize(Decimal('0.01'))
        order.save()

        # If table was available, update status to occupied
        if dining_table and dining_table.status == 'available':
            dining_table.status = 'occupied'
            dining_table.save(update_fields=['status'])

        return order
