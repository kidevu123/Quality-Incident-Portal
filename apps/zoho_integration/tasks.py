from celery import shared_task

from apps.claims.models import Claim
from apps.zoho_integration.models import ZohoSyncLog
from apps.zoho_integration.services import create_replacement_sales_order


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def retry_failed_zoho_push(self, log_id: int, actor_id=None):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    log = ZohoSyncLog.objects.get(pk=log_id)
    if log.action != ZohoSyncLog.Action.REPLACEMENT_SO or not log.claim_id:
        return
    claim = Claim.objects.get(pk=log.claim_id)
    actor = User.objects.filter(pk=actor_id).first() or User.objects.filter(is_superuser=True).first()
    if not actor:
        return
    create_replacement_sales_order(claim=claim, actor=actor)
