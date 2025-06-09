from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

# Import your forms and models
from users.forms import (
    StudentProfileForm,
    SupervisorProfileForm,
)
from users.models import User, StudentProfile, SupervisorProfile


# --- Dashboard Views ---

def student_dashboard_view(request):
    return render(request, 'dashboard/student.html')

def supervisor_dashboard_view(request):
    return render(request, 'dashboard/supervisor.html')

def coordinator_dashboard_view(request):
    return render(request, 'dashboard/coordinator.html')


# --- Profile Update View ---

@method_decorator(login_required, name='dispatch')
class UpdateProfileView(View):
    """
    Handles profile updates for all user types (Students, Supervisors, Coordinators).
    """
    template_name = 'dashboard/update_profile.html'

    def get_form_and_instance(self, user):
        """
        Determines the correct form and profile instance based on user type.
        Handles cases where a profile object might not exist yet.
        """
        if user.user_type == 'supervisor':
            try:
                instance = user.supervisorprofile
            except SupervisorProfile.DoesNotExist:
                instance = None  # Form will create a new instance on POST
            return SupervisorProfileForm, instance

        elif user.user_type == 'student':
            try:
                instance = user.studentprofile
            except StudentProfile.DoesNotExist:
                instance = None  # Form will create a new instance on POST
            return StudentProfileForm, instance

        return None, None

    def get_success_url(self, user):
        """Determines the redirect URL after a successful update."""
        if hasattr(user, 'coordinatorprofile'):
            return reverse('coordinator_dashboard')
        elif hasattr(user, 'supervisorprofile'):
            return reverse('supervisor_dashboard')
        elif hasattr(user, 'studentprofile'):
            return reverse('student_dashboard')
        # Fallback for other users, e.g., redirect to admin panel
        return reverse('admin:index')

    def get(self, request, *args, **kwargs):
        user = request.user
        form_class, instance = self.get_form_and_instance(user)

        if not form_class:
            messages.error(request, "You do not have a profile that can be updated.")
            return redirect('home') # e.g., a generic home page

        form = form_class(instance=instance)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        user = request.user
        form_class, instance = self.get_form_and_instance(user)

        if not form_class:
            messages.error(request, "You do not have a profile that can be updated.")
            return redirect('home')

        form = form_class(request.POST, request.FILES, instance=instance)

        if form.is_valid():
            # If the instance was None, it means we are creating the profile for the first time.
            # We must associate it with the current user before saving.
            if instance is None:
                profile = form.save(commit=False)
                profile.user = user
                profile.save()
                form.save_m2m() # Important for saving many-to-many relationships
            else:
                form.save()

            messages.success(request, "Your profile has been updated successfully.")
            return redirect(self.get_success_url(user))

        # If form is invalid, re-render the page with the form containing errors
        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {'form': form})