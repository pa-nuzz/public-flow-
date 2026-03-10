from django.contrib import admin

from apps.accounts.models import User, SMTPProfile

# Register your models here.
admin.site.register(User)
admin.site.register(SMTPProfile)
