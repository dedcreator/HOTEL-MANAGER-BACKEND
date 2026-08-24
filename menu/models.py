# backend/menu/models.py
import uuid
import datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='🍽️', help_text="Emoji or HeroIcon name e.g. 🍽️, 🍸, CakeIcon")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def item_count(self):
        return self.items.filter(is_available=True).count()


class MenuItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    is_available = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    preparation_time = models.IntegerField(default=15, help_text="Estimated preparation time in minutes")
    image = models.TextField(blank=True, null=True, help_text="Image URL or relative path")
    icon_name = models.CharField(max_length=50, default='CubeIcon', blank=True)
    dietary_tags = models.JSONField(default=list, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.name} - ₦{self.price}"

    @property
    def category_name(self):
        return self.category.name if self.category else ''


class DiningTable(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
        ('cleaning', 'Cleaning'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, help_text="e.g. Table 1 - Main Lounge")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    capacity = models.IntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    section = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Lounge, Poolside, Terrace, Main Hall")
    floor = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. Ground Floor, 1st Floor")
    qr_code = models.TextField(blank=True, null=True)
    qr_code_url = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['table_number']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"table-{self.table_number}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Table {self.table_number} ({self.name})"

    @property
    def menu_url(self):
        return f"/{self.slug}"


class MenuOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('served', 'Served'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
        ('room_charge', 'Room Charge'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, blank=True)
    table = models.ForeignKey(DiningTable, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    customer_name = models.CharField(max_length=200, default='Guest')
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=50, blank=True, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='menu_orders'
    )
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-placed_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            today_str = datetime.date.today().strftime('%Y%m%d')
            last_order = MenuOrder.objects.filter(
                order_number__startswith=f"ORD-{today_str}"
            ).order_by('-order_number').first()

            if last_order and last_order.order_number:
                try:
                    last_num = int(last_order.order_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1

            self.order_number = f"ORD-{today_str}-{new_num:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} (₦{self.total_amount})"

    @property
    def table_number(self):
        return self.table.table_number if self.table else 'N/A'

    def recalculate_totals(self):
        items = self.items.all()
        subtotal = sum(item.subtotal for item in items)
        self.subtotal = subtotal
        self.tax = (Decimal(str(subtotal)) * Decimal('0.075')).quantize(Decimal('0.01'))
        self.total_amount = (Decimal(str(subtotal)) + self.tax - Decimal(str(self.discount))).quantize(Decimal('0.01'))
        self.save(update_fields=['subtotal', 'tax', 'total_amount'])


class MenuOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(MenuOrder, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        qty = Decimal(str(self.quantity))
        unit_p = Decimal(str(self.unit_price))
        self.subtotal = (qty * unit_p).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} x{self.quantity}"
