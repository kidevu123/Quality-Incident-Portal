from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.support.models import NotificationKind, Ticket, TicketMessage
from apps.support.notifications import create_ticket_activity_notifications


def _actor_label(actor) -> str:
    if not actor:
        return "System"
    if hasattr(actor, "get_full_name") and actor.get_full_name():
        return actor.get_full_name()
    if hasattr(actor, "get_username"):
        return actor.get_username()
    return str(actor)


def _short(text: str, limit: int = 240) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


@receiver(pre_save, sender=Ticket)
def remember_ticket_status(sender, instance: Ticket, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        instance._previous_status = Ticket.objects.only("status").get(pk=instance.pk).status
    except Ticket.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Ticket)
def notify_ticket_status_change(sender, instance: Ticket, created: bool, **kwargs):
    if created:
        return
    previous = getattr(instance, "_previous_status", None)
    if not previous or previous == instance.status:
        return
    title = f"{instance.public_id} status changed"
    previous_label = dict(Ticket._meta.get_field("status").choices).get(previous, previous)
    body = f"{previous_label} -> {instance.get_status_display()}"
    create_ticket_activity_notifications(
        ticket=instance,
        actor=None,
        kind=NotificationKind.STATUS,
        title=title,
        body=body,
        include_requester=True,
    )
    from apps.portal.telegram_notify import notify_telegram_ticket_activity

    notify_telegram_ticket_activity(
        instance,
        actor=None,
        title=title,
        body=body,
    )


@receiver(post_save, sender=TicketMessage)
def notify_ticket_message(sender, instance: TicketMessage, created: bool, **kwargs):
    if not created:
        return
    actor = instance.author
    public_or_internal = "internal note" if instance.is_internal else "message"
    title = f"{instance.ticket.public_id} new {public_or_internal}"
    body = f"{_actor_label(actor)}: {_short(instance.body)}"
    create_ticket_activity_notifications(
        ticket=instance.ticket,
        actor=actor,
        kind=NotificationKind.MESSAGE,
        title=title,
        body=body,
        include_requester=not instance.is_internal,
    )
    from apps.portal.telegram_notify import notify_telegram_ticket_activity

    notify_telegram_ticket_activity(
        instance.ticket,
        actor=actor,
        title=title,
        body=body,
    )
