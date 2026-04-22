from django import forms

from apps.claims.models import DefectType, ResolutionRequested, Severity
from apps.crm.models import Batch, CustomerAccount, Product

_field = "mt-1 w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"


class ClaimSubmissionForm(forms.Form):
    customer_account = forms.ModelChoiceField(queryset=CustomerAccount.objects.all())
    retailer_name = forms.CharField(max_length=255)
    contact_name = forms.CharField(max_length=255, required=False)
    contact_email = forms.EmailField(required=False)
    contact_phone = forms.CharField(max_length=64, required=False)
    po_number = forms.CharField(max_length=128, required=False)
    invoice_number = forms.CharField(max_length=128, required=False)
    product = forms.ModelChoiceField(queryset=Product.objects.select_related("manufacturer"))
    batch = forms.ModelChoiceField(
        queryset=Batch.objects.select_related("product"),
        required=False,
    )
    date_sold = forms.DateField(required=False)
    defect_type = forms.ChoiceField(choices=DefectType.choices)
    quantity_sold = forms.IntegerField(min_value=0, required=False)
    quantity_affected = forms.IntegerField(min_value=0, required=False)
    severity = forms.ChoiceField(choices=Severity.choices)
    damage_description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    suspected_root_cause_customer = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    resolution_requested = forms.ChoiceField(choices=ResolutionRequested.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.DateInput)):
                w.attrs.setdefault("class", _field)
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", _field)
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", _field)
