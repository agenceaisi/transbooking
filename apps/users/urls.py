from django.urls import path

from .views import (
    LogoutView,
    TransBookingTokenObtainPairView,
    TransBookingTokenRefreshView,
    UserMeView,
    UserRegistrationView,
)


app_name = "users"

urlpatterns = [
    path("auth/register/", UserRegistrationView.as_view(), name="register"),
    path("auth/login/", TransBookingTokenObtainPairView.as_view(), name="login"),
    path("auth/token/refresh/", TransBookingTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("users/me/", UserMeView.as_view(), name="me"),
]
