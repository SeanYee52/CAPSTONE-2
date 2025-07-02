from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    CustomLoginView,
    CustomPasswordChangeDoneView,
    CustomPasswordChangeView,
    home_view,
)

urlpatterns = [
    # Auth
    path('login/', CustomLoginView.as_view(), name='login'),
    path(
        'password/change/', 
        CustomPasswordChangeView.as_view(), 
        name='password_change'
    ),
    path(
        'password/change/done/', 
        CustomPasswordChangeDoneView.as_view(), 
        name='password_change_done'
    ),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('', home_view, name='home'),
]