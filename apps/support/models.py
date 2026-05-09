from django.conf import settings
from django.db import models


class TicketStatus(models.TextChoices):
    NEW = "new", "New"
    OPEN = "open", "Open"
    PENDING_INFO = "pending_info", "Pending Info"
    INVESTIGATING = "investigating", "Investigating"
    AWAITING_APPROVAL = "awaiting_approval", "Awaiting Approval"
    RESOLVED_CREDIT = "resolved_credit", "Resolved via Credit"
    RESOLVED_REPLACEMENT = "resolved_replacement", "Resolved via Replacement"
    ESCALATED = "escalated", "Escalated"
    CLOSED = "closed", "Closed"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class TicketQueue(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    filter_criteria = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Ticket(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    subject = models.CharField(max_length=512)
    status = models.CharField(
        max_length=32,
        choices=TicketStatus.choices,
        default=TicketStatus.NEW,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
        db_index=True,
    )
    priority_score = models.PositiveSmallIntegerField(default=50)
    queue = models.ForeignKey(
        TicketQueue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_tickets",
    )
    customer_account = models.ForeignKey(
        "crm.CustomerAccount",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    sla_first_response_at = models.DateTimeField(null=True, blank=True)
    sla_resolution_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["customer_account", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} — {self.subject[:48]}"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class NotificationKind(models.TextChoices):
    MESSAGE = "message", "Message"
    STATUS = "status", "Status Change"
    SYSTEM = "system", "System"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="notifications_sent",
        null=True,
        blank=True,
    )
    kind = models.CharField(
        max_length=32,
        choices=NotificationKind.choices,
        default=NotificationKind.SYSTEM,
        db_index=True,
    )
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["ticket", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.recipient} — {self.title}"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} push subscription"


class ResponseMacro(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=64, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
