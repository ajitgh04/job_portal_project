from django.contrib import admin
from .models import Job, JobApplication, UserProfile


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'posted_by', 'location', 'job_type', 'created_at')
    list_filter = ('job_type', 'created_at')
    search_fields = ('title', 'company_name', 'location')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'job', 'status', 'applied_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('user__username', 'job__title', 'job__company_name')
