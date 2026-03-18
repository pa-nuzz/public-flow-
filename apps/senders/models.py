from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
import base64
import hashlib
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

    @staticmethod
    def _normalize_key(raw_key):
        if not raw_key:
            return None
        key = str(raw_key).strip().encode()
        missing_padding = len(key) % 4
        if missing_padding:
            key += b'=' * (4 - missing_padding)
        try:
            base64.urlsafe_b64decode(key)
        except Exception:
            return None
        return key

    @staticmethod
    def _dev_fallback_key():
        secret = getattr(settings, 'SECRET_KEY', '')
        if not secret:
            return None
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())

    def _candidate_fernets(self):
        raw_keys = [
            getattr(settings, 'ENCRYPTION_KEY', ''),
            getattr(settings, 'SMTP_ENCRYPTION_KEY', ''),
        ]

        for raw_key in raw_keys:
            key = self._normalize_key(raw_key)
            if key:
                yield Fernet(key)

        if getattr(settings, 'DEBUG', False):
            dev_key = self._dev_fallback_key()
            if dev_key:
                yield Fernet(dev_key)

    def get_fernet(self):
        """Primary Fernet instance (current ENCRYPTION_KEY)."""
        key = self._normalize_key(getattr(settings, 'ENCRYPTION_KEY', ''))
        if not key:
            raise ValueError("ENCRYPTION_KEY is not set or invalid in settings")
        return Fernet(key)

    def set_password(self, raw_password):
        """Encrypt and set the SMTP password"""
        try:
            f = self.get_fernet()
            # Encrypt the password
            encrypted = f.encrypt(raw_password.encode())
            # Store as base64 string in database
            self._password = base64.urlsafe_b64encode(encrypted).decode()
            logger.info(f"Password encrypted successfully for {self.display_name}")
        except Exception as e:
            logger.error(f"Password encryption error: {e}")
            raise

    def get_password(self):
        """Decrypt and return the SMTP password"""
        if not self._password:
            return None

        ciphertext = self._password.strip().encode()

        for fernet in self._candidate_fernets():
            try:
                encrypted = base64.urlsafe_b64decode(ciphertext)
                decrypted = fernet.decrypt(encrypted).decode()

                primary_fernet = self.get_fernet()
                refreshed = base64.urlsafe_b64encode(primary_fernet.encrypt(decrypted.encode())).decode()
                if refreshed != self._password:
                    self._password = refreshed
                    self.save(update_fields=['_password'])

                return decrypted
            except InvalidToken:
                continue
            except Exception:
                continue

        if getattr(settings, 'DEBUG', False):
            if len(self._password) < 256 and '@' not in self._password and ' ' not in self._password:
                logger.warning(
                    "Sender password for '%s' appears to be stored in plain text. "
                    "Auto-recovering in DEBUG and re-encrypting.",
                    self.display_name,
                )
                plaintext = self._password
                self.set_password(plaintext)
                self.save(update_fields=['_password'])
                return plaintext

        logger.error("Password decryption error for sender '%s'", self.display_name)
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
