import csv
import io
import datetime
import json
import re
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Count, Exists, OuterRef
from django.core.exceptions import ValidationError

# Import your forms and models
from users.forms import (
    StudentProfileForm,
    SupervisorProfileForm,
)
from users.models import User, StudentProfile, SupervisorProfile, CoordinatorProfile
from users.forms import CsvImportForm
from academics.models import Programme, Department, School, Semester, ProgrammePreferenceGroup
from api.models import OriginalTopic, StandardisedTopic

# --- Mixin for security ---
class CoordinatorRequiredMixin(LoginRequiredMixin):
    """
    Ensures that only users with a CoordinatorProfile can access the view.
    """
    def dispatch(self, request, *args, **kwargs):
        # Check if the user has a related CoordinatorProfile.
        is_coordinator = CoordinatorProfile.objects.filter(supervisor__user=request.user).exists() or request.user.is_superuser
        if not is_coordinator:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('home') 
        return super().dispatch(request, *args, **kwargs)

# --- Dashboard Views ---

class StudentDashboardView(LoginRequiredMixin, View):
    login_url = "/login/"
    redirect_field_name = "redirect_to"
    template_name = 'dashboard/student.html'

    def get(self, request, *args, **kwargs):
        try:
            supervisor = SupervisorProfile.objects.get(pk=request.user.studentprofile.supervisor)
        except:
            supervisor = None
        if supervisor:
            context = {"supervisor": supervisor}
        else:
            context = {}
        return render(request, self.template_name, context)

class SupervisorDashboardView(LoginRequiredMixin, View):
    login_url = "/login/"
    redirect_field_name = "redirect_to"
    template_name = 'dashboard/supervisor.html'

    def get(self, request, *args, **kwargs):
        context = {
            'students': [],
            'remaining_capacity': 0,
            'supervisor_profile': None,
            'students_test': StudentProfile.objects.all()
        }

        if hasattr(request.user, 'supervisorprofile'):
            supervisor_profile = request.user.supervisorprofile

            students_queryset = StudentProfile.objects.filter(supervisor=supervisor_profile)

            remaining_capacity = supervisor_profile.supervision_capacity - students_queryset.count()

            context['students'] = students_queryset
            context['remaining_capacity'] = remaining_capacity
            context['supervisor_profile'] = supervisor_profile
        else:
            messages.warning(request, "The logged-in user does not have a supervisor profile.")
        return render(request, self.template_name, context)

#region COORDINATOR VIEWS
class CoordinatorDashboardView(CoordinatorRequiredMixin, View):
    """
    The main overview dashboard for the coordinator.
    Displays summary statistics based on the actual models.
    """
    template_name = 'dashboard/coordinator_master.html'

    def get(self, request, *args, **kwargs):
        # Annotate each supervisor profile with the count of their related students.
        supervisors_with_counts = SupervisorProfile.objects.annotate(
            allocated_student_count=Count('students')
        ).order_by('user__full_name')

        # Annotate with the count of related topics and filter where the count > 0.
        supervisor_with_expertise_count = supervisors_with_counts.filter(
            standardised_expertise__isnull=False
        ).distinct().count()

        # A student is considered "labeled" if they have at least one positive preference.
        students_with_preferences_count = StudentProfile.objects.annotate(
            pref_count=Count('positive_preferences')
        ).filter(
            pref_count__gt=0
        ).count()

        context = {
            'supervisor_with_standardized_expertise_count': supervisor_with_expertise_count,
            'students_with_labeled_preferences_count': students_with_preferences_count,
            'students_allocated_count': StudentProfile.objects.filter(supervisor__isnull=False).count(),
            'students_count': StudentProfile.objects.count(),
            'supervisors_count': supervisors_with_counts.count(),
            'supervisors': supervisors_with_counts,
        }
        return render(request, self.template_name, context)
    
# AJAX Views for Coordinator Actions
class ToggleSupervisorAcceptanceView(CoordinatorRequiredMixin, View):
    """
    Toggles the 'accepting_students' boolean field for a SupervisorProfile via POST request.
    """
    def post(self, request, *args, **kwargs):
        try:
            supervisor_profile = get_object_or_404(SupervisorProfile, pk=kwargs['pk'])
            supervisor_profile.accepting_students = not supervisor_profile.accepting_students
            supervisor_profile.save()
            return JsonResponse({
                'status': 'success',
                'new_state': supervisor_profile.accepting_students
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class UpdateSupervisorCapacityView(CoordinatorRequiredMixin, View):
    """
    Updates the 'supervision_capacity' for a SupervisorProfile via POST request.
    """
    def post(self, request, *args, **kwargs):
        try:
            supervisor_profile = get_object_or_404(SupervisorProfile, pk=kwargs['pk'])
            data = json.loads(request.body)
            new_capacity_str = data.get('capacity')

            if new_capacity_str is None or not str(new_capacity_str).isdigit():
                raise ValidationError("Capacity must be a non-negative integer.")

            supervisor_profile.supervision_capacity = int(new_capacity_str)
            supervisor_profile.full_clean()
            supervisor_profile.save()

            return JsonResponse({
                'status': 'success',
                'new_capacity': supervisor_profile.supervision_capacity
            })
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': '. '.join(e.messages)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# Task Views
class CoordinatorStandardizationView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for the topic standardization task.
    Displays each supervisor's original and standardized expertise.
    """
    template_name = 'dashboard/coordinator_standardize.html'

    def get(self, request, *args, **kwargs):
        supervisors = SupervisorProfile.objects.select_related('user').all().order_by('user__full_name')
        topics = StandardisedTopic.objects.all().order_by('name')
        
        context = {
            'supervisors': supervisors,
            'topics': topics,
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
                student_profiles_query = student_profiles_query.filter(semester__pk=selected_semester_id)
            except (ValueError, TypeError):
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
                student_profiles_query = student_profiles_query.none()

        student_profiles = student_profiles_query.order_by('user__full_name')
        
        context = {
            'semesters': semesters,
            'student_profiles': student_profiles,
            'selected_semester_id': selected_semester_id,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """
        Updates supervisor availability based on the form submission.
        """

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
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
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

class CoordinatorImportView(CoordinatorRequiredMixin, View):
    """
    Provides a page for coordinators to import students and supervisors
    from separate CSV files. Handles both creation of new users and
    updates to existing users.
    """
    template_name = 'dashboard/coordinator_import.html'

    def get(self, request, *args, **kwargs):
        """Displays the two upload forms on the page."""
        context = {
            'student_form': CsvImportForm(),
            'supervisor_form': CsvImportForm(),
            'semesters': Semester.objects.all().order_by('-start_date')
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Handles the form submission for either students or supervisors."""
        if 'import_students' in request.POST:
            return self._handle_student_import(request)
        elif 'import_supervisors' in request.POST:
            return self._handle_supervisor_import(request)
        else:
            messages.error(request, "Invalid submission.")
            return redirect('coordinator_import')

    def _parse_boolean(self, value):
        """Helper to interpret various string representations of a boolean."""
        if isinstance(value, str):
            val = value.lower().strip()
            if val in ('true', '1', 't', 'y', 'yes'):
                return True
            if val in ('false', '0', 'f', 'n', 'no'):
                return False
        return None # Return None for empty or ambiguous values

    def _handle_student_import(self, request):
        """
        Processes the uploaded CSV file for students. Creates or updates records.
        
        Required CSV Headers:
        - 'Full Name'
        - 'Student ID'
        - 'Programme'
        
        Optional CSV Headers:
        - 'Supervisor Email' (Email of the supervisor to assign)
        - 'Preference Text'
        - 'Positive Preferences' (Semicolon-separated list of topic names)
        - 'Negative Preferences' (Semicolon-separated list of topic names)
        - 'Programme Match Type' (Integer)
        - 'Matching Topics' (Semicolon-separated list of topic names)
        - 'Conflicting Topics' (Semicolon-separated list of topic names)
        """
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "There was an error with the form. Please upload a valid CSV file.")
            return redirect('coordinator_import')

        csv_file = form.cleaned_data['csv_file']
        
        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8-sig'))
            headers = set(map(str.strip, reader.fieldnames or []))
            required_headers = {'Full Name', 'Student ID', 'Programme'}
            if not required_headers.issubset(headers):
                messages.error(request, f"CSV for students must have headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        try:
            semester = Semester.objects.get(pk=request.POST.get('semester'))
        except (Semester.DoesNotExist, ValueError, TypeError):
            messages.error(request, "A valid semester must be selected before importing students.")
            return redirect('coordinator_import')

        created_count, updated_count, errors = 0, 0, []
        
        # Define mappings for M2M fields to their CSV headers
        m2m_field_map = {
            'positive_preferences': 'Positive Preferences',
            'negative_preferences': 'Negative Preferences',
            'matching_topics': 'Matching Topics',
            'conflicting_topics': 'Conflicting Topics',
        }

        for i, row in enumerate(reader, start=2):
            try:
                with transaction.atomic():
                    full_name = row.get('Full Name', '').strip()
                    student_id = row.get('Student ID', '').strip().lower()
                    programme_name = row.get('Programme', '').strip()

                    if not all([full_name, student_id, programme_name]):
                        errors.append(f"Row {i}: Missing required data (Full Name, Student ID, or Programme).")
                        continue

                    programme = Programme.objects.get(name__iexact=programme_name)
                    email = f"{student_id}@imail.sunway.edu.my"
                    
                    # --- Prepare data for direct fields and ForeignKeys ---
                    profile_data = {
                        'preference_text': row.get('Preference Text', '').strip() if 'Preference Text' in headers else None
                    }

                    if 'Supervisor Email' in headers and row.get('Supervisor Email', '').strip():
                        supervisor_email = row.get('Supervisor Email').strip()
                        profile_data['supervisor'] = SupervisorProfile.objects.get(user__email__iexact=supervisor_email)
                    
                    if 'Programme Match Type' in headers and row.get('Programme Match Type', '').strip():
                        profile_data['programme_match_type'] = int(row.get('Programme Match Type').strip())

                    # --- Create/Update User and StudentProfile (main object) ---
                    user, user_created = User.objects.get_or_create(
                        email=email,
                        defaults={'full_name': full_name, 'user_type': 'student'}
                    )
                    
                    if user_created:
                        user.set_password("defaultPassword123!") # Consider a more secure default password strategy
                        user.save()
                    else:
                        # Update existing user info if needed
                        user.full_name = full_name
                        user.user_type = 'student'
                        user.save()
                    
                    profile, profile_created = StudentProfile.objects.update_or_create(
                        user=user,
                        defaults={'programme': programme, 'semester': semester, **profile_data}
                    )
                    
                    # --- Handle ManyToManyFields post-creation/update ---
                    for field_name, header_name in m2m_field_map.items():
                        if header_name in headers:
                            topic_names_str = row.get(header_name, '').strip()
                            m2m_manager = getattr(profile, field_name)

                            if not topic_names_str:
                                m2m_manager.clear() # Clear relationship if cell is empty
                                continue

                            # Split by semicolon and strip whitespace from each topic name
                            topic_names = [name.strip() for name in topic_names_str.split(';') if name.strip()]
                            
                            # Find existing topics and set the relationship
                            topics = StandardisedTopic.objects.filter(name__in=topic_names)
                            m2m_manager.set(topics)
                            
                            found_topic_names = {topic.name for topic in topics}
                            missing_topics = set(topic_names) - found_topic_names
                            if missing_topics:
                                errors.append(f"Row {i}: For student {email}, could not find topics: {', '.join(missing_topics)}")

                    if profile_created: created_count += 1
                    else: updated_count += 1

            except Programme.DoesNotExist:
                errors.append(f"Row {i}: Programme '{programme_name}' not found. Skipping.")
            except SupervisorProfile.DoesNotExist:
                errors.append(f"Row {i}: Supervisor with email '{row.get('Supervisor Email')}' not found. Skipping.")
            except (ValueError, TypeError) as e:
                errors.append(f"Row {i}: Invalid data. Check 'Programme Match Type' is a number. Details: {e}")
            except Exception as e:
                errors.append(f"Row {i}: An unexpected database error occurred for student ID {student_id}: {e}")

        # Provide feedback
        if created_count > 0: messages.success(request, f"Successfully created {created_count} new students.")
        if updated_count > 0: messages.info(request, f"Successfully updated {updated_count} existing students.")
        if errors:
            messages.warning(request, "Some rows could not be imported or had warnings. See details below:")
            for error in errors: messages.error(request, error)
        if created_count == 0 and updated_count == 0 and not errors:
            messages.info(request, "The file did not contain any new or updated student information.")
        
        return redirect('coordinator_import')

    
    def _handle_supervisor_import(self, request):
        """
        Processes the uploaded CSV file for supervisors. Creates or updates records.
        
        Required CSV Headers:
        - 'Full Name'
        - 'Email'
        - 'Department' (Name of the Department or School)
        
        Optional CSV Headers:
        - 'Expertise' (Semicolon-separated list of expertise areas)
        - 'Supervision Capacity' (Integer)
        - 'Accepting Students' (True/False, Yes/No, 1/0)
        - 'Standardised Expertise' (Semicolon-separated list of topic names)
        - 'Preferred Programmes First Choice' (Name of the ProgrammePreferenceGroup)
        - 'Preferred Programmes Second Choice' (Name of the ProgrammePreferenceGroup)
        """
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Error with form. Please upload a valid CSV file.")
            return redirect('coordinator_import')
        
        csv_file = form.cleaned_data['csv_file']

        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8-sig'))
            headers = set(map(str.strip, reader.fieldnames or []))
            required_headers = {'Full Name', 'Department', 'Email'}
            if not required_headers.issubset(headers):
                messages.error(request, f"CSV for supervisors must have headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        created_count, updated_count, errors = 0, 0, []

        for i, row in enumerate(reader, start=2):
            try:
                with transaction.atomic():
                    full_name = row.get('Full Name', '').strip()
                    email = row.get('Email', '').strip().lower()
                    org_unit_name = row.get('Department', '').strip()

                    if not all([full_name, email, org_unit_name]):
                        errors.append(f"Row {i}: Missing required data (Full Name, Department, or Email).")
                        continue
                    
                    department, school = None, None
                    try:
                        department = Department.objects.get(name__iexact=org_unit_name)
                        school = department.school
                    except Department.DoesNotExist:
                        school = School.objects.get(name__iexact=org_unit_name)
                    
                    # --- Prepare data for direct fields and ForeignKeys ---
                    profile_data = {}

                    if 'Expertise' in headers:
                        expertise_str = row.get('Expertise', '').strip()
                        # Convert simple semicolon-separated list to the required quoted format
                        expertise_items = [f'"{item.strip()}"' for item in expertise_str.split(';') if item.strip()]
                        profile_data['expertise'] = ", ".join(expertise_items)

                    if 'Supervision Capacity' in headers and row.get('Supervision Capacity', '').strip():
                        profile_data['supervision_capacity'] = int(row.get('Supervision Capacity').strip())
                    
                    if 'Accepting Students' in headers:
                        accepting = self._parse_boolean(row.get('Accepting Students'))
                        if accepting is not None: profile_data['accepting_students'] = accepting
                    
                    if 'Preferred Programmes First Choice' in headers and row.get('Preferred Programmes First Choice', '').strip():
                        group_name = row.get('Preferred Programmes First Choice').strip()
                        profile_data['preferred_programmes_first_choice'] = ProgrammePreferenceGroup.objects.get(name__iexact=group_name)
                    
                    if 'Preferred Programmes Second Choice' in headers and row.get('Preferred Programmes Second Choice', '').strip():
                        group_name = row.get('Preferred Programmes Second Choice').strip()
                        profile_data['preferred_programmes_second_choice'] = ProgrammePreferenceGroup.objects.get(name__iexact=group_name)

                    # --- Create/Update User and SupervisorProfile (main object) ---
                    user, user_created = User.objects.get_or_create(
                        email=email,
                        defaults={'full_name': full_name, 'user_type': 'supervisor'}
                    )
                    if user_created:
                        user.set_password("defaultPassword123!")
                        user.save()
                    else:
                        user.full_name = full_name
                        user.user_type = 'supervisor'
                        user.save()
                    
                    profile, profile_created = SupervisorProfile.objects.update_or_create(
                        user=user,
                        defaults={'department': department, 'school': school, **profile_data}
                    )

                    # --- Handle ManyToManyField ('standardised_expertise') post-creation/update ---
                    if 'Standardised Expertise' in headers:
                        topic_names_str = row.get('Standardised Expertise', '').strip()
                        if not topic_names_str:
                            profile.standardised_expertise.clear()
                        else:
                            topic_names = [name.strip() for name in topic_names_str.split(';') if name.strip()]
                            topics = StandardisedTopic.objects.filter(name__in=topic_names)
                            profile.standardised_expertise.set(topics)
                            
                            found_topic_names = {topic.name for topic in topics}
                            missing_topics = set(topic_names) - found_topic_names
                            if missing_topics:
                                errors.append(f"Row {i}: For supervisor {email}, could not find standardised topics: {', '.join(missing_topics)}")

                    if profile_created: created_count += 1
                    else: updated_count += 1

            except (Department.DoesNotExist, School.DoesNotExist):
                errors.append(f"Row {i}: Department/School '{org_unit_name}' not found. Skipping.")
            except ProgrammePreferenceGroup.DoesNotExist as e:
                errors.append(f"Row {i}: A Programme Preference Group was not found. Details: {e}")
            except (ValueError, TypeError):
                errors.append(f"Row {i}: Invalid 'Supervision Capacity'. It must be a whole number. Skipping.")
            except Exception as e:
                errors.append(f"Row {i}: An unexpected database error occurred for supervisor {email}: {e}")

        # Provide feedback
        if created_count > 0: messages.success(request, f"Successfully created {created_count} new supervisors.")
        if updated_count > 0: messages.info(request, f"Successfully updated {updated_count} existing supervisors.")
        if errors:
            messages.warning(request, "Some rows could not be imported or had warnings. See details below:")
            for error in errors: messages.error(request, error)
        if created_count == 0 and updated_count == 0 and not errors:
            messages.info(request, "The file did not contain any new or updated supervisor information.")
            
        return redirect('coordinator_import')

class CoordinatorExportView(CoordinatorRequiredMixin, View):
    """
    Handles exporting student or supervisor data to a CSV file.
    The exported file is formatted to be re-importable by CoordinatorImportView.
    """

    def get(self, request, *args, **kwargs):
        """
        Determines whether to export students or supervisors based on the URL.
        """
        user_type = kwargs.get('user_type')
        if user_type == 'students':
            return self._export_students(request)
        elif user_type == 'supervisors':
            return self._export_supervisors(request)
        else:
            messages.error(request, "Invalid export type specified.")
            return redirect('dashboard') # Or some other appropriate page

    def _export_students(self, request):
        """
        Generates and returns a CSV file of all student data.
        """
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="students_export_{datetime.date.today()}.csv"'},
        )

        writer = csv.writer(response)
        header = [
            'Student ID', 'Full Name', 'Programme', 'Supervisor Email',
            'Preference Text', 'Positive Preferences', 'Negative Preferences',
            'Programme Match Type', 'Matching Topics', 'Conflicting Topics'
        ]
        writer.writerow(header)

        def _format_m2m_for_csv(manager):
            """Helper to format a ManyToMany related manager into a semicolon-separated string."""
            return "; ".join([topic.name for topic in manager.all()])

        # Optimize query to fetch related data in one go
        # Use select_related for FK/OneToOne and prefetch_related for M2M/Reverse FK
        students = StudentProfile.objects.select_related(
            'user', 'programme', 'supervisor__user'
        ).prefetch_related(
            'positive_preferences',
            'negative_preferences',
            'matching_topics',
            'conflicting_topics'
        ).all()

        for profile in students:
            writer.writerow([
                profile.student_id,
                profile.user.full_name,
                profile.programme.name if profile.programme else '',
                profile.supervisor.user.email if profile.supervisor and profile.supervisor.user else '',
                profile.preference_text or '',
                _format_m2m_for_csv(profile.positive_preferences),
                _format_m2m_for_csv(profile.negative_preferences),
                profile.programme_match_type if profile.programme_match_type is not None else '',
                _format_m2m_for_csv(profile.matching_topics),
                _format_m2m_for_csv(profile.conflicting_topics),
            ])

        return response

    def _export_supervisors(self, request):
        """
        Generates and returns a CSV file of all supervisor data.
        """
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="supervisors_export_{datetime.date.today()}.csv"'},
        )

        writer = csv.writer(response)
        header = [
            'Email', 'Full Name', 'Department', 'Supervision Capacity',
            'Accepting Students', 'Expertise', 'Standardised Expertise',
            'Preferred Programmes First Choice', 'Preferred Programmes Second Choice'
        ]
        writer.writerow(header)

        def _format_expertise_for_csv(expertise_str):
            """
            Parses the database format ' "item1", "item2" ' into 'item1; item2'.
            """
            if not expertise_str:
                return ""
            # Find all content within quotes
            items = re.findall(r'"([^"]*)"', expertise_str)
            return "; ".join(items)
        
        def _format_m2m_for_csv(manager):
            """Helper to format a ManyToMany related manager into a semicolon-separated string."""
            return "; ".join([item.name for item in manager.all()])

        # Optimize query to fetch all related data efficiently
        supervisors = SupervisorProfile.objects.select_related(
            'user', 'department', 'school',
            'preferred_programmes_first_choice', 'preferred_programmes_second_choice'
        ).prefetch_related('standardised_expertise').all()

        for profile in supervisors:
            # The import function checks for Department name first, then School name.
            # Export the Department name if it exists, otherwise the School name.
            org_unit_name = profile.department.name if profile.department else \
                            (profile.school.name if profile.school else '')

            writer.writerow([
                profile.user.email,
                profile.user.full_name,
                org_unit_name,
                profile.supervision_capacity,
                'Yes' if profile.accepting_students else 'No',
                _format_expertise_for_csv(profile.expertise),
                _format_m2m_for_csv(profile.standardised_expertise),
                profile.preferred_programmes_first_choice.name if profile.preferred_programmes_first_choice else '',
                profile.preferred_programmes_second_choice.name if profile.preferred_programmes_second_choice else '',
            ])
            
        return response

class DeleteStudentsBySemesterView(CoordinatorRequiredMixin, View):
    """
    Provides a page for coordinators to delete all students from a selected semester.
    This is a destructive action and requires explicit confirmation.
    """
    template_name = 'dashboard/delete_students_confirmation.html'

    def get(self, request, *args, **kwargs):
        """
        Displays the confirmation page with a list of semesters.
        """
        context = {
            'semesters': Semester.objects.all().order_by('-start_date')
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handles the deletion of students for the selected semester.
        """
        semester_id = request.POST.get('semester')
        confirmation = request.POST.get('confirmation_check')

        # Security Check: Ensure the user explicitly confirmed the action.
        if not confirmation:
            messages.error(request, "You must check the confirmation box to proceed with the deletion.")
            return redirect('delete_students_by_semester')

        if not semester_id:
            messages.error(request, "You must select a semester.")
            return redirect('delete_students_by_semester')

        try:
            semester = Semester.objects.get(pk=semester_id)
        except Semester.DoesNotExist:
            messages.error(request, "The selected semester is invalid.")
            return redirect('delete_students_by_semester')

        # Find the users to be deleted.
        # Deleting the User will cascade and delete the associated StudentProfile.
        users_to_delete = User.objects.filter(
            studentprofile__semester=semester,
            user_type='student' # Extra safeguard
        )
        
        count = users_to_delete.count()

        if count > 0:
            try:
                with transaction.atomic():
                    # The .delete() method returns the number of objects deleted and a dictionary with details.
                    deleted_count, _ = users_to_delete.delete()
                
                messages.success(request, f"Successfully deleted {count} students and their accounts from the semester: {semester.name}.")
            except Exception as e:
                 messages.error(request, f"An error occurred during deletion: {e}")
        else:
            messages.info(request, f"No students were found in the semester '{semester.name}' to delete.")

        return redirect('coordinator_import') # Redirect back to the main import/export page

#region PROFILE UPDATE
@method_decorator(login_required, name='dispatch')
class UpdateProfileView(View):
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
        if hasattr(user, 'supervisorprofile'):
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