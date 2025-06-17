# api/urls.py
from django.urls import path
from .views import StartStandardizationView, StartLabelingView, TaskStatusView

urlpatterns = [
    # Endpoint for Task 1
    path('start-standardization/', StartStandardizationView.as_view(), name='start_standardization'),
    
    # Endpoint for Task 2
    path('start-labeling/', StartLabelingView.as_view(), name='start_labeling'),

    # Endpoint for Task Status
    path('coordinator/task-status/<str:task_id>/', TaskStatusView.as_view(), name='task_status'),
]