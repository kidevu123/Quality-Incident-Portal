from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import Customer360ViewSet, TicketViewSet

router = DefaultRouter()
router.register(r"tickets", TicketViewSet, basename="ticket")
router.register(r"customers", Customer360ViewSet, basename="customer360")

urlpatterns = [
    path("", include(router.urls)),
]
