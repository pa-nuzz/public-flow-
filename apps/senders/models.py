from django.db import models
from django.conf import settings
from django.core import signing
from cryptography.fernet import Fernet
import os
import base64
import logging

logger = logging.getLogger(__name__)


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

    def get_fernet(self):
        """Get Fernet instance using key from settings"""
        try:
            key = settings.ENCRYPTION_KEY
            if not key:
                raise ValueError("ENCRYPTION_KEY is not set in settings")

            # Ensure key is a string and strip any whitespace
            if isinstance(key, str):
                key = key.strip()

            # Ensure the key has correct padding
            # Fernet keys should already be properly padded, but just in case
            key_bytes = key.encode()

            # Add padding if necessary (Fernet keys should already be padded)
            try:
                # Test if key is valid base64
                base64.urlsafe_b64decode(key_bytes)
            except Exception as e:
                logger.error(f"Invalid base64 key format: {e}")
                # If padding is incorrect, try to fix it
                missing_padding = len(key_bytes) % 4
                if missing_padding:
                    key_bytes += b'=' * (4 - missing_padding)
                    logger.info(f"Added padding to key, new length: {len(key_bytes)}")

            return Fernet(key_bytes)

        except Exception as e:
            logger.error(f"Fernet initialization error: {e}")
            raise

    def set_password(self, raw_password):
        """Encrypt and set the SMTP password"""
        try:
            f = self.get_fernet()
            # Encrypt the password
            encrypted = f.encrypt(raw_password.encode())
            # Store as base64 string in database
            self.smtp_password = base64.urlsafe_b64encode(encrypted).decode()
            logger.info(f"Password encrypted successfully for {self.display_name}")
        except Exception as e:
            logger.error(f"Password encryption error: {e}")
            raise

    def get_password(self):
        """Decrypt and return the SMTP password"""
        try:
            if not self.smtp_password:
                return None

            f = self.get_fernet()
            # Decode from base64 and decrypt
            encrypted = base64.urlsafe_b64decode(self.smtp_password.encode())
            decrypted = f.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Password decryption error: {e}")
            return None

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
