from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Q, Exists, OuterRef

# Import your forms and models
from users.forms import (
    StudentProfileForm,
    SupervisorProfileForm,
)
from users.models import User, StudentProfile, SupervisorProfile, CoordinatorProfile
from academics.models import Semester

# --- Mixin for security ---
class CoordinatorRequiredMixin(LoginRequiredMixin):
    """
    Ensures that only users with a CoordinatorProfile can access the view.
    """
    def dispatch(self, request, *args, **kwargs):
        # Check if the user has a related CoordinatorProfile.
        # This is more robust than checking is_staff.
        is_coordinator = CoordinatorProfile.objects.filter(supervisor__user=request.user).exists() or request.user.is_superuser
        if not is_coordinator:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('home') 
        return super().dispatch(request, *args, **kwargs)

# --- Dashboard Views ---

def student_dashboard_view(request):
    # This view is not changed
    return render(request, 'dashboard/student.html')

def supervisor_dashboard_view(request):
    # This view is not changed
    return render(request, 'dashboard/supervisor.html')

class CoordinatorDashboardView(CoordinatorRequiredMixin, View):
    """
    The main overview dashboard for the coordinator.
    Displays summary statistics based on the actual models.
    """
    template_name = 'dashboard/coordinator_master.html'

    def get(self, request, *args, **kwargs):
        supervisors_with_standardized_expertise_count = SupervisorProfile.objects.exclude(
            Q(standardised_expertise__isnull=True) | Q(standardised_expertise__exact='')
        ).count()

        students_with_labeled_preferences_count = StudentProfile.objects.filter(
            Q(positive_preferences__isnull=False) & ~Q(positive_preferences='') &
            Q(negative_preferences__isnull=False) & ~Q(negative_preferences='')
        ).count()

        context = {
            'supervisor_with_standardized_expertise_count': supervisors_with_standardized_expertise_count,
            'students_with_labeled_preferences_count': students_with_labeled_preferences_count,
        }
        return render(request, self.template_name, context)

class CoordinatorStandardizationView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for the topic standardization task.
    Displays each supervisor's original and standardized expertise.
    """
    template_name = 'dashboard/coordinator_standardize.html'

    def get(self, request, *args, **kwargs):
        supervisors = SupervisorProfile.objects.select_related('user').all().order_by('user__full_name')
        
        context = {
            'supervisors': supervisors,
        }
        return render(request, self.template_name, context)

class CoordinatorLabelingView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for the student preference labeling task.
    Displays each student's original text and their resulting positive/negative labels.
    The list of students can be filtered by semester.
    """
    template_name = 'dashboard/coordinator_label.html'

    def get(self, request, *args, **kwargs):
        semesters = Semester.objects.all().order_by('-start_date')
        
        # Get the selected semester ID from the URL query parameters
        selected_semester_id_str = request.GET.get('semester')
        selected_semester_id = None

        # Base query for student profiles
        student_profiles_query = StudentProfile.objects.select_related('user', 'semester')

        if selected_semester_id_str:
            try:
                selected_semester_id = int(selected_semester_id_str)
                student_profiles_query = student_profiles_query.filter(semester_id=selected_semester_id)
            except (ValueError, TypeError):
                # If the parameter is invalid, show no profiles
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
                # If there are no semesters at all, show no profiles
                student_profiles_query = student_profiles_query.none()

        student_profiles = student_profiles_query.order_by('user__full_name')
        
        context = {
            'semesters': semesters,
            'student_profiles': student_profiles,
            'selected_semester_id': selected_semester_id, # Pass the selected ID to the template
        }
        return render(request, self.template_name, context)

class CoordinatorMatchingView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for student to supervisor matching task.
    Displays each student and their assigned supervisor.
    List of students can be filtered by semester.
    """

    template_name = 'dashboard/coordinator_match.html'

    def get(self, request, *args, **kwargs):
        semesters = Semester.objects.all().order_by('-start_date')
        
        # Get the selected semester ID from the URL query parameters
        selected_semester_id_str = request.GET.get('semester')
        selected_semester_id = None

        # Base query for student profiles
        student_profiles_query = StudentProfile.objects.select_related('user', 'semester')

        if selected_semester_id_str:
            try:
                selected_semester_id = int(selected_semester_id_str)
                student_profiles_query = student_profiles_query.filter(semester_id=selected_semester_id)
            except (ValueError, TypeError):
                # If the parameter is invalid, show no profiles
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
                # If there are no semesters at all, show no profiles
                student_profiles_query = student_profiles_query.none()

        student_profiles = student_profiles_query.order_by('user__full_name')
        supervisor_profiles = SupervisorProfile.objects.filter(Exists(StudentProfile.objects.filter(supervisor=OuterRef('pk'))))
        context = {
            'semesters': semesters,
            'student_profiles': student_profiles,
            'supervisor_profiles': supervisor_profiles,
            'selected_semester_id': selected_semester_id,
        }
        return render(request, self.template_name, context)

#region PROFILE UPDATE
@method_decorator(login_required, name='dispatch')
class UpdateProfileView(View):
    # This class remains the same as in your provided code
    template_name = 'dashboard/update_profile.html'

    def get_form_and_instance(self, user):
        """
        Determines the correct form and profile instance based on user type.
        Handles cases where a profile object might not exist yet.
        """
        if hasattr(user, 'supervisorprofile'):
            return SupervisorProfileForm, user.supervisorprofile
        elif hasattr(user, 'studentprofile'):
            return StudentProfileForm, user.studentprofile
        return None, None
    
    def get_success_url(self, user):
        """Determines the redirect URL after a successful update."""
        if CoordinatorProfile.objects.filter(supervisor__user=user).exists():
            return reverse('coordinator_dashboard')
        elif hasattr(user, 'supervisorprofile'):
            return reverse('supervisor_dashboard')
        elif hasattr(user, 'studentprofile'):
            return reverse('student_dashboard')
        return reverse('home')

    def get(self, request, *args, **kwargs):
        user = request.user
        form_class, instance = self.get_form_and_instance(user)
        if not form_class:
            messages.error(request, "You do not have a profile that can be updated.")
            return redirect('home') 
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
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect(self.get_success_url(user))
        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {'form': form})