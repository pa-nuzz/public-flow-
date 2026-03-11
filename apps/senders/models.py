from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import os

class Sender(models.Model):
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail / Google Workspace'),
        ('outlook', 'Outlook / Office 365'),
        ('custom', 'Custom SMTP'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='senders')
    display_name = models.CharField(max_length=255)
    from_email = models.EmailField()
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='gmail')
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.PositiveIntegerField(default=587)
    username = models.CharField(max_length=255)
    _password = models.TextField(db_column='password')  # encrypted
    use_tls = models.BooleanField(default=True)
    daily_limit = models.PositiveIntegerField(default=500)
    emails_sent_today = models.PositiveIntegerField(default=0)
    last_reset_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        key = settings.SMTP_ENCRYPTION_KEY.encode()
        f = Fernet(key)
        self._password = f.encrypt(raw_password.encode()).decode()

    def get_password(self):
        key = settings.SMTP_ENCRYPTION_KEY.encode()
        f = Fernet(key)
        return f.decrypt(self._password.encode()).decode()

    @property
    def is_limit_reached(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.last_reset_date != today:
            self.emails_sent_today = 0
            self.last_reset_date = today
            self.save(update_fields=['emails_sent_today', 'last_reset_date'])
        return self.emails_sent_today >= self.daily_limit

    class Meta:
        unique_together = ('user', 'from_email')

    def __str__(self):
        return f"{self.display_name} <{self.from_email}>"
