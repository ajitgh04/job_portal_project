from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ApplicationStatusForm, JobForm, RegistrationForm
from .models import Job, JobApplication, UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect('jobs:job_list')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('jobs:job_list')

    return render(request, 'jobs/register.html', {'form': form})


def _require_recruiter(request):
    if not UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.RECRUITER,
    ).exists():
        raise PermissionDenied('Only recruiters can access the recruiter dashboard.')


@login_required
def recruiter_dashboard(request):
    _require_recruiter(request)
    jobs = request.user.recruiter_jobs.annotate(
        application_count=Count('applications'),
    ).order_by('-created_at')
    recent_applications = JobApplication.objects.filter(
        job__posted_by=request.user,
    ).select_related('job', 'user').order_by('-applied_at')[:8]
    return render(
        request,
        'jobs/recruiter_dashboard.html',
        {
            'jobs': jobs,
            'job_count': jobs.count(),
            'application_count': JobApplication.objects.filter(
                job__posted_by=request.user,
            ).count(),
            'pending_count': JobApplication.objects.filter(
                job__posted_by=request.user,
                status=JobApplication.Status.PENDING,
            ).count(),
            'recent_applications': recent_applications,
        },
    )


@login_required
def recruiter_job_create(request):
    _require_recruiter(request)
    form = JobForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        job = form.save(commit=False)
        job.posted_by = request.user
        job.save()
        messages.success(request, 'Your job posting has been published.')
        return redirect('jobs:recruiter_dashboard')
    return render(
        request,
        'jobs/recruiter_job_form.html',
        {'form': form, 'heading': 'Post a job', 'submit_label': 'Publish job'},
    )


@login_required
def recruiter_job_edit(request, job_id):
    _require_recruiter(request)
    job = get_object_or_404(Job, pk=job_id, posted_by=request.user)
    form = JobForm(request.POST or None, instance=job)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your job posting has been updated.')
        return redirect('jobs:recruiter_dashboard')
    return render(
        request,
        'jobs/recruiter_job_form.html',
        {'form': form, 'job': job, 'heading': 'Edit job', 'submit_label': 'Save changes'},
    )


@login_required
def recruiter_job_delete(request, job_id):
    _require_recruiter(request)
    job = get_object_or_404(Job, pk=job_id, posted_by=request.user)
    if request.method == 'POST':
        job.delete()
        messages.success(request, 'The job posting and its applications were deleted.')
        return redirect('jobs:recruiter_dashboard')
    return render(request, 'jobs/recruiter_job_confirm_delete.html', {'job': job})


@login_required
def recruiter_job_applicants(request, job_id):
    _require_recruiter(request)
    job = get_object_or_404(Job, pk=job_id, posted_by=request.user)
    applications = job.applications.select_related('user').order_by('-applied_at')
    return render(
        request,
        'jobs/recruiter_applicants.html',
        {
            'job': job,
            'applications': applications,
            'status_choices': JobApplication.Status.choices,
        },
    )


@login_required
@require_POST
def recruiter_update_application_status(request, application_id):
    _require_recruiter(request)
    application = get_object_or_404(
        JobApplication,
        pk=application_id,
        job__posted_by=request.user,
    )
    form = ApplicationStatusForm(request.POST, instance=application)
    if form.is_valid():
        form.save()
        messages.success(request, 'Applicant status has been updated.')
    else:
        messages.error(request, 'Choose a valid applicant status.')
    return redirect('jobs:recruiter_job_applicants', job_id=application.job_id)


def job_list(request):
    jobs = Job.objects.order_by('-created_at')
    is_job_seeker = request.user.is_authenticated and UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.JOB_SEEKER,
    ).exists()
    if is_job_seeker:
        jobs = jobs.annotate(
            has_applied=Exists(
                JobApplication.objects.filter(
                    user=request.user,
                    job_id=OuterRef('pk'),
                )
            )
        )

    return render(
        request,
        'jobs/job_list.html',
        {'jobs': jobs, 'is_job_seeker': is_job_seeker},
    )


def job_detail(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    is_job_seeker = request.user.is_authenticated and UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.JOB_SEEKER,
    ).exists()
    already_applied = is_job_seeker and JobApplication.objects.filter(
        user=request.user,
        job=job,
    ).exists()

    return render(
        request,
        'jobs/job_detail.html',
        {
            'job': job,
            'is_job_seeker': is_job_seeker,
            'already_applied': already_applied,
        },
    )


@login_required
@require_POST
def apply_to_job(request, job_id):
    if not UserProfile.objects.filter(
        user=request.user,
        role=UserProfile.Role.JOB_SEEKER,
    ).exists():
        raise PermissionDenied('Only job seekers can apply for jobs.')

    job = get_object_or_404(Job, pk=job_id)
    application, created = JobApplication.objects.get_or_create(
        user=request.user,
        job=job,
    )

    if created:
        messages.success(request, 'Your application has been submitted.')
    else:
        messages.info(request, 'You have already applied for this job.')

    return redirect('jobs:job_detail', job_id=job.pk)
