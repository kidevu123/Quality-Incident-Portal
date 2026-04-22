from django.contrib import admin

from .models import Batch, CustomerAccount, EndCustomer, Manufacturer, Product, SalesOrder, SalesOrderLine


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 0


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    search_fields = ("name", "external_id", "zoho_account_id")
    list_display = ("name", "claim_rate_percent", "abuse_risk_score", "sales_volume_ytd")


@admin.register(EndCustomer)
class EndCustomerAdmin(admin.ModelAdmin):
    list_filter = ("distributor",)
    search_fields = ("retailer_name", "email")


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    search_fields = ("name", "code")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_filter = ("manufacturer",)
    search_fields = ("sku", "description")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_filter = ("hot_flag", "product__manufacturer")
    search_fields = ("lot_number",)


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    inlines = [SalesOrderLineInline]
    search_fields = ("number", "po_number", "invoice_number", "zoho_id")
