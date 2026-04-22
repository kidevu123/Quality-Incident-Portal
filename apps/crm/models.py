from django.db import models


class CustomerAccount(models.Model):
    """Distributor / B2B account."""

    name = models.CharField(max_length=255)
    external_id = models.CharField(max_length=128, blank=True, db_index=True)
    zoho_account_id = models.CharField(max_length=64, blank=True, db_index=True)
    sales_volume_ytd = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    claim_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    abuse_risk_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Customer account"
        verbose_name_plural = "Customer accounts"

    def __str__(self) -> str:
        return self.name


class EndCustomer(models.Model):
    retailer_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    distributor = models.ForeignKey(
        CustomerAccount,
        on_delete=models.CASCADE,
        related_name="end_customers",
    )

    class Meta:
        ordering = ["retailer_name"]

    def __str__(self) -> str:
        return self.retailer_name


class Manufacturer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=32, unique=True)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True)
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name="products",
    )
    zoho_item_id = models.CharField(max_length=64, blank=True, db_index=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["sku"]

    def __str__(self) -> str:
        return self.sku


class Batch(models.Model):
    lot_number = models.CharField(max_length=128, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    manufactured_on = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    hot_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ["-manufactured_on"]
        unique_together = [["lot_number", "product"]]
        verbose_name_plural = "Batches"

    def __str__(self) -> str:
        return f"{self.lot_number} ({self.product.sku})"


class SalesOrder(models.Model):
    """Original or linked Zoho sales order."""

    number = models.CharField(max_length=64, unique=True, db_index=True)
    zoho_id = models.CharField(max_length=64, blank=True, db_index=True)
    customer = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    po_number = models.CharField(max_length=128, blank=True)
    invoice_number = models.CharField(max_length=128, blank=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=64, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-ordered_at"]

    def __str__(self) -> str:
        return self.number


class SalesOrderLine(models.Model):
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        unique_together = [["sales_order", "product"]]
