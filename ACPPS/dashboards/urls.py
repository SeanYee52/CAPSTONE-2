# dashboards/urls.py

from django.urls import path
from .views import (
    StudentDashboardView,
    SupervisorDashboardView,
    CoordinatorDashboardView,
    CoordinatorStandardizationView,
    CoordinatorLabelingView,
    UpdateProfileView,
    CoordinatorMatchingView,
    CoordinatorImportView,
    CoordinatorExportView,
    DeleteStudentsBySemesterView,
    ToggleSupervisorAcceptanceView,
    UpdateSupervisorCapacityView,
)

urlpatterns = [
    path('student/', StudentDashboardView.as_view(), name='student_dashboard'),
    path('supervisor/', SupervisorDashboardView.as_view(), name='supervisor_dashboard'),

    # --- Coordinator URL Structure ---
    path('coordinator/', CoordinatorDashboardView.as_view(), name='coordinator_dashboard'),
    path('coordinator/standardize/', CoordinatorStandardizationView.as_view(), name='coordinator_standardize'),
    path('coordinator/label/', CoordinatorLabelingView.as_view(), name='coordinator_label'),
    path('coordinator/match/', CoordinatorMatchingView.as_view(), name='coordinator_match'),
    path('coordinator/import/', CoordinatorImportView.as_view(), name='coordinator_import'),
    path('export/<str:user_type>/', CoordinatorExportView.as_view(), name='coordinator_export'),
    path('students/delete-by-semester/', DeleteStudentsBySemesterView.as_view(), name='delete_students_by_semester'),

    path('supervisor/<int:pk>/toggle-acceptance/', ToggleSupervisorAcceptanceView.as_view(), name='toggle_supervisor_acceptance'),
    path('supervisor/<int:pk>/update-capacity/', UpdateSupervisorCapacityView.as_view(), name='update_supervisor_capacity'),

    path('update-profile/', UpdateProfileView.as_view(), name='update_profile'),
]