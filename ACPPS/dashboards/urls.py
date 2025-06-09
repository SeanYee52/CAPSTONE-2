from django.urls import path
from . import views

urlpatterns = [
    path('student/', views.student_dashboard_view, name='student_dashboard'),
    path('supervisor/', views.supervisor_dashboard_view, name='supervisor_dashboard'),
    path('coordinator/', views.coordinator_dashboard_view, name='coordinator_dashboard'),
    path('profile/update/', views.UpdateProfileView.as_view(), name='update_profile'),
]