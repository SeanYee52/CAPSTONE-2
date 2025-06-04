# academics/urls.py
from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Faculty URLs
    path('faculties/', views.FacultyListView.as_view(), name='faculty_list'),
    path('faculties/add/', views.FacultyCreateView.as_view(), name='faculty_add'),
    path('faculties/<int:pk>/edit/', views.FacultyUpdateView.as_view(), name='faculty_edit'),

    # School URLs
    path('schools/', views.SchoolListView.as_view(), name='school_list'),
    path('schools/add/', views.SchoolCreateView.as_view(), name='school_add'),
    path('schools/<int:pk>/edit/', views.SchoolUpdateView.as_view(), name='school_edit'),

    # Department URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/add/', views.DepartmentCreateView.as_view(), name='department_add'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_edit'),

    # Programme URLs
    path('programmes/', views.ProgrammeListView.as_view(), name='programme_list'),
    path('programmes/add/', views.ProgrammeCreateView.as_view(), name='programme_add'),
    path('programmes/<int:pk>/edit/', views.ProgrammeUpdateView.as_view(), name='programme_edit'),

    # ProgrammePreferenceGroup URLs
    path('preference-groups/', views.ProgrammePreferenceGroupListView.as_view(), name='preferencegroup_list'),
    path('preference-groups/add/', views.ProgrammePreferenceGroupCreateView.as_view(), name='preferencegroup_add'),
    path('preference-groups/<int:pk>/edit/', views.ProgrammePreferenceGroupUpdateView.as_view(), name='preferencegroup_edit'),
]