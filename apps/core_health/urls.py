from django.urls import path

from . import views

urlpatterns = [
    path("live/", views.health_live, name="health_live"),
    path("ready/", views.health_ready, name="health_ready"),
]
