from decimal import Decimal

from django import forms

from apps.claims.models import DefectType, ResolutionRequested, Severity
from apps.crm.models import Batch, CustomerAccount, Manufacturer, Product

_field = "mt-1 w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"


class DataListTextInput(forms.TextInput):
    """Text input with HTML5 datalist id (render matching <datalist> in the template)."""

    def __init__(self, datalist_id: str, attrs=None):
        super().__init__(attrs)
        self.datalist_id = datalist_id

    def render(self, name, value, attrs=None, renderer=None):
        merged = self.build_attrs(self.attrs, attrs)
        merged["list"] = self.datalist_id
        return super().render(name, value, merged, renderer)


class ClaimSubmissionForm(forms.Form):
    customer_account = forms.CharField(
        label="Customer account",
        max_length=255,
        widget=DataListTextInput("dl-customer-accounts", attrs={"class": _field, "autocomplete": "off"}),
        help_text="Type your distributor account name. Pick a suggestion or enter a new name.",
    )
    retailer_name = forms.CharField(max_length=255)
    contact_name = forms.CharField(max_length=255, required=False)
    contact_email = forms.EmailField(required=False)
    contact_phone = forms.CharField(max_length=64, required=False)
    po_number = forms.CharField(max_length=128, required=False)
    invoice_number = forms.CharField(max_length=128, required=False)
    product_sku = forms.CharField(
        label="Product (SKU)",
        max_length=128,
        widget=DataListTextInput("dl-product-skus", attrs={"class": _field, "autocomplete": "off"}),
        help_text="Type the SKU from the product label. Pick a suggestion or enter any SKU.",
    )
    product_description = forms.CharField(
        label="Product description (optional)",
        max_length=500,
        required=False,
        help_text="Helps staff if this SKU is new to the catalog.",
    )
    batch_lot = forms.CharField(
        label="Batch / lot number",
        max_length=128,
        required=False,
        widget=DataListTextInput("dl-batch-lots", attrs={"class": _field, "autocomplete": "off"}),
        help_text="Optional. Type the lot code from the packaging, or pick a suggestion.",
    )
    date_sold = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": _field},
        ),
        input_formats=["%Y-%m-%d"],
    )
    defect_type = forms.ChoiceField(choices=DefectType.choices)
    quantity_sold = forms.IntegerField(min_value=0, required=False)
    quantity_affected = forms.IntegerField(min_value=0, required=False)
    estimated_financial_impact = forms.DecimalField(
        label="Estimated financial impact (USD, optional)",
        max_digits=14,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
        help_text=(
            "Approximate credit, refund, or replacement value you expect. "
            "If you leave this blank, we estimate from catalog unit price × affected quantity when available."
        ),
    )
    severity = forms.ChoiceField(choices=Severity.choices)
    damage_description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    suspected_root_cause_customer = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    resolution_requested = forms.ChoiceField(choices=ResolutionRequested.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_account"].widget.attrs.setdefault("placeholder", "Type or choose from list…")
        self.fields["product_sku"].widget.attrs.setdefault("placeholder", "Type or choose from list…")
        self.fields["batch_lot"].widget.attrs.setdefault("placeholder", "Type or choose from list…")
        efi = self.fields.get("estimated_financial_impact")
        if efi:
            efi.widget.attrs.setdefault("class", _field)
            efi.widget.attrs.setdefault("step", "0.01")
            efi.widget.attrs.setdefault("min", "0")
            efi.widget.attrs.setdefault("placeholder", "e.g. 125.00")
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, DataListTextInput):
                continue
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.DateInput)):
                w.attrs.setdefault("class", _field)
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", _field)
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", _field)

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        acc_name = (cleaned.get("customer_account") or "").strip()
        if not acc_name:
            self.add_error("customer_account", "Enter your customer / distributor account name.")
            return cleaned

        account = CustomerAccount.objects.filter(name__iexact=acc_name).first()
        if not account:
            account, _ = CustomerAccount.objects.get_or_create(
                name=acc_name,
                defaults={"notes": "Created from distributor portal (typed / not in catalog)."},
            )
        self._resolved_customer_account = account

        sku = (cleaned.get("product_sku") or "").strip()
        if not sku:
            self.add_error("product_sku", "Enter the product SKU.")
            return cleaned

        product = Product.objects.filter(sku__iexact=sku).first()
        if not product:
            desc = (cleaned.get("product_description") or "").strip()
            mfr, _ = Manufacturer.objects.get_or_create(
                code="PORTAL",
                defaults={"name": "Portal — unlisted catalog"},
            )
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={"description": desc, "manufacturer": mfr},
            )
            if desc and not product.description:
                product.description = desc
                product.save(update_fields=["description"])
        self._resolved_product = product

        lot = (cleaned.get("batch_lot") or "").strip()
        self._resolved_batch = None
        if lot:
            self._resolved_batch, _ = Batch.objects.get_or_create(
                lot_number=lot,
                product=self._resolved_product,
                defaults={},
            )

        return cleaned
