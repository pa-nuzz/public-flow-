from django.db import models
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

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
    recipient_emails = models.TextField(blank=True, default='')
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
    
    # A/B Testing Fields
    is_ab_test = models.BooleanField(default=False)
    ab_test_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed')],
        default='pending'
    )
    ab_test_duration_hours = models.PositiveIntegerField(default=2)
    winner_variant = models.ForeignKey('CampaignVariant', null=True, blank=True, on_delete=models.SET_NULL, related_name='won_campaigns')
    
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

    def get_recipient_list(self):
        recipients = []
        for item in (self.recipient_emails or '').replace(';', ',').replace('\n', ',').split(','):
            email = item.strip().lower()
            if not email:
                continue
            try:
                validate_email(email)
            except ValidationError:
                continue
            if email not in recipients:
                recipients.append(email)
        return recipients


class CampaignVariant(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='variants')
    label = models.CharField(max_length=1)  # 'A', 'B'
    subject = models.CharField(max_length=998)
    body_html = models.TextField(blank=True, default='')
    body_text = models.TextField(blank=True, default='')
    percentage = models.PositiveIntegerField(default=10)  # E.g., 10% of total list
    sent_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    bounce_count = models.PositiveIntegerField(default=0)
    spam_score = models.FloatField(null=True, blank=True)
    spam_risk = models.CharField(max_length=10, choices=Campaign.RISK_CHOICES, default='low')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('campaign', 'label')

    def __str__(self):
        return f"{self.campaign.name} - Variant {self.label}"

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


class EmailEngagement(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='engagements')
    campaign_variant = models.ForeignKey(CampaignVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name='engagements')
    recipient_email = models.EmailField()
    tracking_token = models.CharField(max_length=64, unique=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=['tracking_token']),
            models.Index(fields=['campaign', 'recipient_email']),
            models.Index(fields=['recipient_email']),  # For recipient lookups
            models.Index(fields=['sent_at']),
            models.Index(fields=['opened_at']),  # For open rate queries
            models.Index(fields=['clicked_at']),  # For click rate queries
        ]

    def __str__(self):
        return f"{self.recipient_email} - {self.campaign.name}"


class EmailClickEvent(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='click_events')
    engagement = models.ForeignKey(EmailEngagement, on_delete=models.CASCADE, related_name='click_events')
    clicked_url = models.URLField(max_length=2048)
    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['campaign', 'clicked_at']),
            models.Index(fields=['campaign', 'clicked_url']),
        ]

    def __str__(self):
        return f"{self.campaign.name} -> {self.clicked_url}"


class EmailTemplate(models.Model):
    """Reusable email templates like Gmail templates."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_templates')
    name = models.CharField(max_length=255, help_text="Template name (e.g., 'Welcome Email', 'Monthly Newsletter')")
    subject = models.CharField(max_length=998, blank=True, help_text="Email subject line")
    body_html = models.TextField(blank=True, help_text="HTML version of the email")
    body_text = models.TextField(blank=True, help_text="Plain text version")
    is_active = models.BooleanField(default=True)
    use_count = models.PositiveIntegerField(default=0, help_text="How many times this template was used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-use_count', '-updated_at']
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name

    def increment_use(self):
        self.use_count += 1
        self.save(update_fields=['use_count'])