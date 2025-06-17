from django.urls import path
from .views import AcademicAdminView, AcademicDashboardView

app_name = 'academics'

urlpatterns = [
    path('', AcademicDashboardView.as_view(), name='dashboard'),

    # List View: e.g., /academics/faculty/
    path('<str:model_name>/', AcademicAdminView.as_view(), name='admin_list'),
    
    # Create View: e.g., /academics/faculty/add/
    path('<str:model_name>/add/', AcademicAdminView.as_view(), name='admin_create'),

    # Update View: e.g., /academics/faculty/1/edit/
    path('<str:model_name>/<int:pk>/edit/', AcademicAdminView.as_view(), name='admin_update'),
]