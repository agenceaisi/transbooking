"""Project URL configuration."""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter


api_router = DefaultRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include(api_router.urls)),
]
