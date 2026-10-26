from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full-time'
        PART_TIME = 'part_time', 'Part-time'
        REMOTE = 'remote', 'Remote'

    title = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    job_type = models.CharField(max_length=10, choices=JobType.choices)
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    requirements = models.TextField()
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recruiter_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} at {self.company_name}'


class UserProfile(models.Model):
    class Role(models.TextChoices):
        JOB_SEEKER = 'job_seeker', 'Job Seeker'
        RECRUITER = 'recruiter', 'Recruiter'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=Role.choices)

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


class JobApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'New'
        REVIEWING = 'reviewing', 'Reviewing'
        INTERVIEW = 'interview', 'Interview'
        REJECTED = 'rejected', 'Rejected'
        HIRED = 'hired', 'Hired'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='job_applications',
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'job'],
                name='unique_job_application_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.job.title}'
