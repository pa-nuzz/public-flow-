from django.db import models
from django.conf import settings

class Campaign(models.Model):
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=998)
    body_html = models.TextField()
    body_text = models.TextField()
    from_name = models.CharField(max_length=255)
    reply_to = models.CharField(max_length=254)
    status = models.CharField(max_length=20)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    total_recipients = models.IntegerField()
    sent_count = models.IntegerField()
    spam_score = models.FloatField(blank=True, null=True)
    spam_risk = models.CharField(max_length=10)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.DO_NOTHING)

    class Meta:
        db_table = 'campaigns_campaign'

    def __str__(self):
        return self.name
