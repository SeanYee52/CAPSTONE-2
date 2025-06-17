from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from celery.result import AsyncResult

# Import the two independent tasks
from .tasks import standardize_all_topics, label_student_preferences_for_semester

class StartStandardizationView(APIView):
    """API endpoint to trigger the topic standardization task."""
    permission_classes = [IsAdminUser]

    def post(self, request, *format):
        # Capture the task object returned by .delay()
        task = standardize_all_topics.delay()
        return Response(
            {
                "message": "Topic standardization task has been initiated in the background.",
                "task_id": task.id  # Include the task ID in the response
            },
            status=status.HTTP_202_ACCEPTED
        )

class StartLabelingView(APIView):
    """API endpoint to trigger the student preference labeling task."""
    permission_classes = [IsAdminUser]

    def post(self, request, *format):
        semester = request.data.get('semester')
        if not semester:
            return Response(
                {"error": "A 'semester' parameter is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Capture the task object returned by .delay()
        task = label_student_preferences_for_semester.delay(semester=semester)
        return Response(
            {
                "message": f"Student preference labeling for semester '{semester}' has been initiated.",
                "task_id": task.id # Include the task ID in the response
            },
            status=status.HTTP_202_ACCEPTED
        )
    
class TaskStatusView(APIView):
    """
    Checks the status of a Celery task given its ID.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, task_id, *format):
        task_result = AsyncResult(task_id)
        
        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'result': None
        }

        if task_result.successful():
            response_data['result'] = task_result.result
        elif task_result.failed():
            # The result of a failed task is the Exception object.
            # Convert it to a string for the JSON response.
            response_data['result'] = str(task_result.result)
        
        # If status is PENDING, result will be None, which is correct.
        return Response(response_data, status=status.HTTP_200_OK)