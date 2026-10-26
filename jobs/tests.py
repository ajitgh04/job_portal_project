from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from .models import Job, JobApplication, UserProfile


class JobPortalModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='applicant')
        self.job = Job.objects.create(
            title='Developer',
            company_name='Example Co.',
            description='Build software.',
            location='Remote',
            job_type=Job.JobType.REMOTE,
            salary=75000,
            requirements='Django experience',
        )

    def test_job_fields_and_created_at(self):
        self.assertEqual(self.job.title, 'Developer')
        self.assertEqual(self.job.job_type, Job.JobType.REMOTE)
        self.assertLessEqual(self.job.created_at, timezone.now())

    def test_user_profile_role(self):
        profile = UserProfile.objects.create(
            user=self.user,
            role=UserProfile.Role.JOB_SEEKER,
        )

        self.assertEqual(self.user.profile, profile)
        self.assertEqual(profile.get_role_display(), 'Job Seeker')

    def test_job_application_links_user_and_job(self):
        application = JobApplication.objects.create(user=self.user, job=self.job)

        self.assertIn(application, self.user.job_applications.all())
        self.assertIn(application, self.job.applications.all())
        self.assertLessEqual(application.applied_at, timezone.now())

    def test_user_cannot_apply_to_same_job_twice(self):
        JobApplication.objects.create(user=self.user, job=self.job)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JobApplication.objects.create(user=self.user, job=self.job)


class JobViewTests(TestCase):
    def setUp(self):
        self.seeker = User.objects.create_user(username='seeker', password='password')
        UserProfile.objects.create(
            user=self.seeker,
            role=UserProfile.Role.JOB_SEEKER,
        )
        self.job = Job.objects.create(
            title='Developer',
            company_name='Example Co.',
            description='Build software.',
            location='Remote',
            job_type=Job.JobType.REMOTE,
            requirements='Django experience',
        )

    def test_job_list_displays_jobs_newest_first(self):
        older_job = Job.objects.create(
            title='Older role',
            company_name='Other Co.',
            description='An older job.',
            location='On-site',
            job_type=Job.JobType.FULL_TIME,
            requirements='Experience',
        )
        older_job.created_at = self.job.created_at - timedelta(days=1)
        older_job.save(update_fields=['created_at'])

        response = self.client.get(reverse('jobs:job_list'))

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response.content.index(b'Developer'),
            response.content.index(b'Older role'),
        )
        self.assertIn(self.job, response.context['jobs'])
        self.assertIn(older_job, response.context['jobs'])

    def test_job_seeker_can_apply_from_job_list(self):
        self.client.force_login(self.seeker)

        response = self.client.get(reverse('jobs:job_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Apply now')
        self.assertContains(
            response,
            reverse('jobs:apply_to_job', args=[self.job.pk]),
        )

    def test_job_list_shows_applied_state(self):
        JobApplication.objects.create(user=self.seeker, job=self.job)
        self.client.force_login(self.seeker)

        response = self.client.get(reverse('jobs:job_list'))

        self.assertContains(response, 'Applied')
        self.assertNotContains(response, 'Apply now')

    def test_job_detail_displays_job(self):
        self.client.force_login(self.seeker)
        response = self.client.get(
            reverse('jobs:job_detail', args=[self.job.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job.title)
        self.assertContains(response, 'Apply for this job')

    def test_seeker_can_apply_and_duplicate_submission_is_safe(self):
        self.client.force_login(self.seeker)
        url = reverse('jobs:apply_to_job', args=[self.job.pk])

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('jobs:job_detail', args=[self.job.pk]),
        )
        self.assertTrue(
            JobApplication.objects.filter(user=self.seeker, job=self.job).exists()
        )

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('jobs:job_detail', args=[self.job.pk]),
        )
        self.assertEqual(
            JobApplication.objects.filter(user=self.seeker, job=self.job).count(),
            1,
        )

    def test_non_seeker_cannot_apply(self):
        recruiter = User.objects.create_user(username='recruiter', password='password')
        UserProfile.objects.create(
            user=recruiter,
            role=UserProfile.Role.RECRUITER,
        )
        self.client.force_login(recruiter)

        response = self.client.post(
            reverse('jobs:apply_to_job', args=[self.job.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            JobApplication.objects.filter(user=recruiter, job=self.job).exists()
        )

    def test_application_requires_login_and_post(self):
        url = reverse('jobs:apply_to_job', args=[self.job.pk])

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            f'/accounts/login/?next={url}',
        )

        self.client.force_login(self.seeker)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class AuthenticationViewTests(TestCase):
    def registration_data(self, role):
        return {
            'username': f'{role}_account',
            'email': f'{role}@example.com',
            'role': role,
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        }

    def test_registration_creates_user_profile_and_signs_user_in(self):
        for role in (UserProfile.Role.JOB_SEEKER, UserProfile.Role.RECRUITER):
            with self.subTest(role=role):
                response = self.client.post(
                    reverse('jobs:register'),
                    self.registration_data(role),
                )

                user = User.objects.get(username=f'{role}_account')
                self.assertEqual(user.profile.role, role)
                self.assertTrue(user.check_password('ComplexPass123!'))
                self.assertTrue(response.wsgi_request.user.is_authenticated)
                self.assertRedirects(response, reverse('jobs:job_list'))
                self.client.logout()

    def test_registration_rejects_invalid_role(self):
        data = self.registration_data('administrator')

        response = self.client.post(reverse('jobs:register'), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='administrator_account').exists())
        self.assertContains(response, 'Select a valid choice')

    def test_login_and_logout(self):
        user = User.objects.create_user(
            username='recruiter',
            password='ComplexPass123!',
        )
        UserProfile.objects.create(user=user, role=UserProfile.Role.RECRUITER)

        response = self.client.post(
            reverse('jobs:login'),
            {'username': 'recruiter', 'password': 'ComplexPass123!'},
        )

        self.assertRedirects(response, reverse('jobs:job_list'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        response = self.client.post(reverse('jobs:logout'))

        self.assertRedirects(response, reverse('jobs:job_list'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class RecruiterDashboardTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(
            username='recruiter',
            password='password',
        )
        UserProfile.objects.create(
            user=self.recruiter,
            role=UserProfile.Role.RECRUITER,
        )
        self.other_recruiter = User.objects.create_user(
            username='other_recruiter',
            password='password',
        )
        UserProfile.objects.create(
            user=self.other_recruiter,
            role=UserProfile.Role.RECRUITER,
        )
        self.seeker = User.objects.create_user(
            username='candidate',
            email='candidate@example.com',
            password='password',
        )
        UserProfile.objects.create(
            user=self.seeker,
            role=UserProfile.Role.JOB_SEEKER,
        )
        self.job = Job.objects.create(
            title='Backend Engineer',
            company_name='Example Co.',
            description='Build services.',
            location='Remote',
            job_type=Job.JobType.REMOTE,
            requirements='Django experience',
            posted_by=self.recruiter,
        )
        self.other_job = Job.objects.create(
            title='Private listing',
            company_name='Other Co.',
            description='Another role.',
            location='Remote',
            job_type=Job.JobType.REMOTE,
            requirements='Experience',
            posted_by=self.other_recruiter,
        )
        self.application = JobApplication.objects.create(
            user=self.seeker,
            job=self.job,
        )

    def test_dashboard_is_recruiter_only_and_shows_owned_metrics(self):
        response = self.client.get(reverse('jobs:recruiter_dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('jobs:login')}?next={reverse('jobs:recruiter_dashboard')}",
        )

        self.client.force_login(self.seeker)
        self.assertEqual(
            self.client.get(reverse('jobs:recruiter_dashboard')).status_code,
            403,
        )

        self.client.force_login(self.recruiter)
        response = self.client.get(reverse('jobs:recruiter_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['job_count'], 1)
        self.assertEqual(response.context['application_count'], 1)
        self.assertEqual(response.context['pending_count'], 1)
        self.assertContains(response, 'Backend Engineer')
        self.assertNotContains(response, 'Private listing')
        self.assertContains(response, 'candidate@example.com')

    def test_recruiter_can_create_and_update_owned_job(self):
        self.client.force_login(self.recruiter)
        job_data = {
            'title': 'Product Designer',
            'company_name': 'Example Co.',
            'description': 'Design products.',
            'location': 'Hybrid',
            'job_type': Job.JobType.FULL_TIME,
            'salary': '90000',
            'requirements': 'Portfolio required.',
        }

        response = self.client.post(
            reverse('jobs:recruiter_job_create'),
            job_data,
        )
        created_job = Job.objects.get(title='Product Designer')
        self.assertRedirects(response, reverse('jobs:recruiter_dashboard'))
        self.assertEqual(created_job.posted_by, self.recruiter)

        response = self.client.post(
            reverse('jobs:recruiter_job_edit', args=[self.job.pk]),
            {**job_data, 'title': 'Senior Backend Engineer'},
        )
        self.assertRedirects(response, reverse('jobs:recruiter_dashboard'))
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, 'Senior Backend Engineer')

        response = self.client.get(
            reverse('jobs:recruiter_job_edit', args=[self.other_job.pk]),
        )
        self.assertEqual(response.status_code, 404)

    def test_recruiter_can_review_applicants_and_update_status(self):
        self.client.force_login(self.recruiter)
        applicants_url = reverse(
            'jobs:recruiter_job_applicants',
            args=[self.job.pk],
        )
        response = self.client.get(applicants_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'candidate@example.com')

        response = self.client.post(
            reverse(
                'jobs:recruiter_update_application_status',
                args=[self.application.pk],
            ),
            {'status': JobApplication.Status.INTERVIEW},
        )

        self.assertRedirects(response, applicants_url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.INTERVIEW)

        self.client.force_login(self.other_recruiter)
        self.assertEqual(self.client.get(applicants_url).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse(
                    'jobs:recruiter_update_application_status',
                    args=[self.application.pk],
                ),
                {'status': JobApplication.Status.HIRED},
            ).status_code,
            404,
        )

    def test_recruiter_can_delete_owned_job_and_applications(self):
        self.client.force_login(self.recruiter)
        delete_url = reverse('jobs:recruiter_job_delete', args=[self.job.pk])

        self.assertEqual(self.client.get(delete_url).status_code, 200)
        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse('jobs:recruiter_dashboard'))
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())
        self.assertFalse(JobApplication.objects.filter(pk=self.application.pk).exists())
        self.assertEqual(
            self.client.post(
                reverse('jobs:recruiter_job_delete', args=[self.other_job.pk]),
            ).status_code,
            404,
        )
