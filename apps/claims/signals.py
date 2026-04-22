from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.quality.models import QualityIncident

from .models import Claim


@receiver(post_save, sender=Claim)
def hot_batch_watch(sender, instance: Claim, created: bool, **kwargs):
    if not instance.batch_id:
        return
    threshold = getattr(settings, "HOT_BATCH_CLAIM_THRESHOLD", 3)
    count = Claim.objects.filter(batch_id=instance.batch_id).count()
    if count < threshold:
        return
    batch = instance.batch
    if batch.hot_flag:
        return
    batch.hot_flag = True
    batch.save(update_fields=["hot_flag"])
    if QualityIncident.objects.filter(batch=batch, status="open").exists():
        return
    from apps.support.utils import generate_token

    QualityIncident.objects.create(
        public_id=generate_token("INC"),
        batch=batch,
        title=f"Hot batch threshold — {batch.lot_number}",
        triggered_by_threshold=True,
        claim_count_at_open=count,
    )
