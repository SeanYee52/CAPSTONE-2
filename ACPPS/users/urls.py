from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    CustomLoginView,
    home_view,
)

urlpatterns = [
    # Auth
    path('login/', CustomLoginView.as_view(), name='login'),
    # Django's built-in LogoutView is usually sufficient.
    # LOGOUT_REDIRECT_URL must be set in settings.py for this to work seamlessly.
    path('logout/', LogoutView.as_view(), name='logout'),

    # A generic home page
    path('', home_view, name='home'),
]