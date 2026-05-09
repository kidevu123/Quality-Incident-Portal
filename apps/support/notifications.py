"""Ticket activity notifications for web and Telegram."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.support.models import Notification, NotificationKind, Ticket


STAFF_NOTIFICATION_ROLES = (
    Role.ADMIN,
    Role.AGENT,
    Role.QUALITY,
    Role.FINANCE,
)


def ticket_url_for_user(ticket: Ticket, user: User) -> str:
    if user.is_superuser or user.role in STAFF_NOTIFICATION_ROLES:
        return reverse("ticket_workspace", kwargs={"public_id": ticket.public_id})
    return reverse("portal_ticket", kwargs={"public_id": ticket.public_id})


def ticket_activity_recipients(ticket: Ticket, *, actor=None, include_requester: bool = True) -> list[User]:
    qs = User.objects.filter(
        Q(is_superuser=True) | Q(role__in=STAFF_NOTIFICATION_ROLES),
        is_active=True,
    )
    if include_requester and ticket.requester_id:
        qs = qs | User.objects.filter(pk=ticket.requester_id, is_active=True)
    if ticket.assignee_id:
        qs = qs | User.objects.filter(pk=ticket.assignee_id, is_active=True)
    if actor and getattr(actor, "pk", None):
        qs = qs.exclude(pk=actor.pk)
    return list(qs.distinct())


def create_ticket_activity_notifications(
    *,
    ticket: Ticket,
    actor=None,
    kind: str = NotificationKind.SYSTEM,
    title: str,
    body: str = "",
    include_requester: bool = True,
) -> None:
    notifications = [
        Notification(
            recipient=user,
            ticket=ticket,
            actor=actor if getattr(actor, "pk", None) else None,
            kind=kind,
            title=title[:160],
            body=body[:1200],
            url=ticket_url_for_user(ticket, user),
        )
        for user in ticket_activity_recipients(
            ticket,
            actor=actor,
            include_requester=include_requester,
        )
    ]
    if notifications:
        created = Notification.objects.bulk_create(notifications)
        from apps.support.push import send_web_push_for_notifications

        send_web_push_for_notifications(created)


def unread_notification_count(user) -> int:
    if not getattr(user, "is_authenticated", False):
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()
