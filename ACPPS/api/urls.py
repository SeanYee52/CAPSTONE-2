# api/urls.py
from django.urls import path
from .views import StartStandardizationView, StartLabelingView, TaskStatusView, StartMatchingView, ResetMatchingView, ResetTopicMappingView

urlpatterns = [
    # Endpoint for Tasks
    path('start-standardization/', StartStandardizationView.as_view(), name='start_standardization'),
    path('start-matching/', StartMatchingView.as_view(), name="start_matching"),
    path('start-labeling/', StartLabelingView.as_view(), name='start_labeling'),
    path('reset-matching/', ResetMatchingView.as_view(), name='reset_matches'),
    path('reset-topics/', ResetTopicMappingView.as_view(), name='reset_topics'),
    path('coordinator/task-status/<str:task_id>/', TaskStatusView.as_view(), name='task_status'),
]