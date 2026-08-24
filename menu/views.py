# backend/menu/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from decimal import Decimal
import datetime

from .models import Category, MenuItem, DiningTable, MenuOrder, MenuOrderItem
from .serializers import (
    CategorySerializer,
    MenuItemSerializer,
    DiningTableSerializer,
    MenuOrderSerializer,
    CreateMenuOrderSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('sort_order', 'name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Category.objects.all()
        # For public/anonymous, only show active
        if self.request.user.is_anonymous:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('sort_order', 'name')


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all().order_by('sort_order', 'name')
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = MenuItem.objects.select_related('category').all()
        
        category_id = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        is_available = self.request.query_params.get('is_available')

        if category_id and category_id != 'all':
            import uuid
            try:
                cat_uuid = uuid.UUID(str(category_id))
                queryset = queryset.filter(
                    Q(category_id=cat_uuid) | Q(category__name__iexact=category_id)
                )
            except (ValueError, AttributeError, TypeError):
                queryset = queryset.filter(category__name__iexact=category_id)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        if is_available is not None:
            queryset = queryset.filter(is_available=is_available.lower() == 'true')
        elif self.request.user.is_anonymous:
            # By default for public users, only show available items
            queryset = queryset.filter(is_available=True)

        return queryset.order_by('sort_order', 'name')

    @action(detail=True, methods=['post'])
    def toggle_availability(self, request, pk=None):
        item = self.get_object()
        item.is_available = not item.is_available
        item.save(update_fields=['is_available'])
        return Response({'success': True, 'is_available': item.is_available})


class DiningTableViewSet(viewsets.ModelViewSet):
    queryset = DiningTable.objects.all().order_by('table_number')
    serializer_class = DiningTableSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = DiningTable.objects.all()
        if self.request.user.is_anonymous:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('table_number')

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        table = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(DiningTable.STATUS_CHOICES):
            table.status = new_status
            table.save(update_fields=['status'])
            return Response(DiningTableSerializer(table).data)
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)


class MenuOrderViewSet(viewsets.ModelViewSet):
    queryset = MenuOrder.objects.all().order_by('-placed_at')
    serializer_class = MenuOrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = MenuOrder.objects.select_related('table', 'staff').prefetch_related('items__menu_item').all()
        
        table_param = self.request.query_params.get('table')
        order_status = self.request.query_params.get('status')
        payment_status = self.request.query_params.get('payment_status')
        date_param = self.request.query_params.get('date')

        if table_param:
            import uuid
            try:
                table_uuid = uuid.UUID(str(table_param))
                queryset = queryset.filter(
                    Q(table__id=table_uuid) | Q(table__slug=table_param) | Q(table__table_number=table_param)
                )
            except (ValueError, AttributeError, TypeError):
                queryset = queryset.filter(
                    Q(table__slug=table_param) | Q(table__table_number=table_param)
                )

        if order_status:
            queryset = queryset.filter(status=order_status)

        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        if date_param:
            queryset = queryset.filter(placed_at__date=date_param)

        return queryset.order_by('-placed_at')

    def create(self, request, *args, **kwargs):
        serializer = CreateMenuOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output_serializer = MenuOrderSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes')

        if new_status in dict(MenuOrder.STATUS_CHOICES):
            order.status = new_status
            if notes:
                order.notes = f"{order.notes}\n{notes}".strip()
            order.save()

            # If order is completed/served/paid, table can be freed or kept
            if new_status in ['served', 'paid'] and order.table:
                # If all orders for table are paid or served
                active_orders = MenuOrder.objects.filter(
                    table=order.table,
                    status__in=['pending', 'preparing', 'ready']
                ).exclude(id=order.id)
                if not active_orders.exists() and new_status == 'paid':
                    order.table.status = 'available'
                    order.table.save(update_fields=['status'])

            return Response(MenuOrderSerializer(order).data)
        return Response({'error': f'Invalid status: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        payment_method = request.data.get('payment_method', 'cash')
        
        order.payment_status = 'paid'
        order.payment_method = payment_method
        if order.status in ['pending', 'preparing', 'ready', 'served']:
            order.status = 'paid'
        order.save()

        # Free table if no other active orders
        if order.table:
            active_orders = MenuOrder.objects.filter(
                table=order.table,
                status__in=['pending', 'preparing', 'ready', 'served']
            ).exclude(id=order.id)
            if not active_orders.exists():
                order.table.status = 'available'
                order.table.save(update_fields=['status'])

        return Response(MenuOrderSerializer(order).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        today = datetime.date.today()
        today_orders = MenuOrder.objects.filter(placed_at__date=today)
        
        active_count = MenuOrder.objects.filter(status__in=['pending', 'preparing', 'ready']).count()
        pending_count = MenuOrder.objects.filter(status='pending').count()
        preparing_count = MenuOrder.objects.filter(status='preparing').count()
        ready_count = MenuOrder.objects.filter(status='ready').count()
        served_count = today_orders.filter(status='served').count()
        paid_count = today_orders.filter(payment_status='paid').count()

        today_revenue = today_orders.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')

        return Response({
            'active_orders': active_count,
            'pending_orders': pending_count,
            'preparing_orders': preparing_count,
            'ready_orders': ready_count,
            'served_today': served_count,
            'paid_today': paid_count,
            'today_revenue': float(today_revenue),
            'total_tables': DiningTable.objects.count(),
            'occupied_tables': DiningTable.objects.filter(status='occupied').count(),
        })


# ============= PUBLIC STANDALONE ENDPOINTS =============

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_categories(request):
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_items(request):
    category_id = request.query_params.get('category')
    search = request.query_params.get('search')

    queryset = MenuItem.objects.filter(is_available=True).select_related('category')
    
    if category_id and category_id != 'all':
        queryset = queryset.filter(
            Q(category_id=category_id) | Q(category__name__iexact=category_id)
        )
    
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    serializer = MenuItemSerializer(queryset.order_by('sort_order', 'name'), many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_tables(request):
    tables = DiningTable.objects.filter(is_active=True).order_by('table_number')
    serializer = DiningTableSerializer(tables, many=True)
    return Response(serializer.data)
