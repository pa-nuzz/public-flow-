from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    full_name = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)



class SMTPProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255) # NOTE: Dev A needs to encrypt this!
    is_active = models.BooleanField(default=True)
    daily_limit = models.IntegerField(default=100)

    def __str__(self):
        return self.email