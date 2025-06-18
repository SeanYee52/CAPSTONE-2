# dashboards/urls.py

from django.urls import path
from .views import (
    student_dashboard_view,
    supervisor_dashboard_view,
    CoordinatorDashboardView,
    CoordinatorStandardizationView,
    CoordinatorLabelingView,
    UpdateProfileView,
    CoordinatorMatchingView
)

urlpatterns = [
    path('student/', student_dashboard_view, name='student_dashboard'),
    path('supervisor/', supervisor_dashboard_view, name='supervisor_dashboard'),

    # --- Coordinator URL Structure ---
    path('coordinator/', CoordinatorDashboardView.as_view(), name='coordinator_dashboard'),
    path('coordinator/standardize/', CoordinatorStandardizationView.as_view(), name='coordinator_standardize'),
    path('coordinator/label/', CoordinatorLabelingView.as_view(), name='coordinator_label'),
    path('coordinator/match/', CoordinatorMatchingView.as_view(), name='coordinator_match'),

    path('update-profile/', UpdateProfileView.as_view(), name='update_profile'),
]