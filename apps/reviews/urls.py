from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompanyReviewViewSet, ReviewViewSet


app_name = "reviews"

router = DefaultRouter()
router.register("reviews", ReviewViewSet, basename="reviews")
router.register("company/reviews", CompanyReviewViewSet, basename="company-reviews")

urlpatterns = [
    path("", include(router.urls)),
]
