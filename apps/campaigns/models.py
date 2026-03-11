from django.db import models
from django.conf import settings

class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('paused', 'Paused'),
        ('failed', 'Failed'),
    ]
    RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaigns')
    sender = models.ForeignKey('senders.Sender', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=998)
    body_html = models.TextField(blank=True, default='')
    body_text = models.TextField(blank=True, default='')
    from_name = models.CharField(max_length=255, blank=True)
    reply_to = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(blank=True, null=True)
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    bounce_count = models.PositiveIntegerField(default=0)
    spam_score = models.FloatField(null=True, blank=True)
    spam_risk = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def open_rate(self):
        if self.sent_count == 0:
            return 0
        return round((self.open_count / self.sent_count) * 100, 1)

    @property
    def bounce_rate(self):
        if self.sent_count == 0:
            return 0
        return round((self.bounce_count / self.sent_count) * 100, 1)