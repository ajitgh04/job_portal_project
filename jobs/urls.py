from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import StyledAuthenticationForm

from . import views

app_name = 'jobs'

urlpatterns = [
    path('accounts/register/', views.register, name='register'),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='jobs/login.html',
            authentication_form=StyledAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(next_page='jobs:job_list'),
        name='logout',
    ),
    path('recruiter/', views.recruiter_dashboard, name='recruiter_dashboard'),
    path('recruiter/jobs/new/', views.recruiter_job_create, name='recruiter_job_create'),
    path(
        'recruiter/jobs/<int:job_id>/edit/',
        views.recruiter_job_edit,
        name='recruiter_job_edit',
    ),
    path(
        'recruiter/jobs/<int:job_id>/delete/',
        views.recruiter_job_delete,
        name='recruiter_job_delete',
    ),
    path(
        'recruiter/jobs/<int:job_id>/applicants/',
        views.recruiter_job_applicants,
        name='recruiter_job_applicants',
    ),
    path(
        'recruiter/applications/<int:application_id>/status/',
        views.recruiter_update_application_status,
        name='recruiter_update_application_status',
    ),
    path('', views.job_list, name='job_list'),
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),
    path('jobs/<int:job_id>/apply/', views.apply_to_job, name='apply_to_job'),
]
