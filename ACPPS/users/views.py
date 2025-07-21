from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.shortcuts import render

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
            if user.is_superuser:
                return reverse_lazy('admin:index') # Redirect superusers to admin panel
            elif user.user_type == 'supervisor':
                # Check if the supervisor is also a coordinator
                if hasattr(user.supervisorprofile, 'coordinatorprofile'):
                    return reverse_lazy('coordinator_dashboard')
                return reverse_lazy('supervisor_dashboard')
            elif user.user_type == 'student':
                return reverse_lazy('student_dashboard')

        # Fallback for any other case
        return reverse_lazy('home')

class CustomPasswordChangeView(PasswordChangeView):
    """
    Handles the form for a user to change their own password.
    This view automatically uses Django's built-in PasswordChangeForm
    and requires the user to be logged in.
    """
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('password_change_done') # Redirect here on success

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    """
    Displays a success message after the user has changed their password.
    """
    template_name = 'users/password_change_done.html'

def home_view(request):
    return render(request, 'pages/home.html')

