# users/views.py
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.shortcuts import render # For placeholder dashboard views

from .forms import UserLoginForm

class CustomLoginView(LoginView):
    """
    A custom login view that uses the UserLoginForm (email-based auth)
    and redirects users to different dashboards based on their user type.
    """
    form_class = UserLoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True # Redirect if user is already logged in

    def get_success_url(self):
        """
        Redirect users to the appropriate dashboard after login.
        """
        user = self.request.user
        if user.is_authenticated:
            if user.is_superuser or user.is_staff:
                return reverse_lazy('admin:index') # Redirect staff/superusers to admin panel
            elif user.user_type == 'supervisor':
                # Check if the supervisor is also a coordinator
                if hasattr(user.supervisorprofile, 'coordinatorprofile'):
                    return reverse_lazy('coordinator_dashboard')
                return reverse_lazy('supervisor_dashboard')
            elif user.user_type == 'student':
                return reverse_lazy('student_dashboard')

        # Fallback for any other case
        return reverse_lazy('home')

# --- Placeholder views for redirection ---
# In a real application, these would be in their respective apps/views.

def home_view(request):
    return render(request, 'pages/home.html')

