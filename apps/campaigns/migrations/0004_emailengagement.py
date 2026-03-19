from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0003_campaign_recipient_emails'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailEngagement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(max_length=254)),
                ('tracking_token', models.CharField(max_length=64, unique=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('open_count', models.PositiveIntegerField(default=0)),
                ('click_count', models.PositiveIntegerField(default=0)),
                ('last_event_at', models.DateTimeField(blank=True, null=True)),
                ('campaign', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='engagements', to='campaigns.campaign')),
            ],
        ),
        migrations.AddIndex(
            model_name='emailengagement',
            index=models.Index(fields=['tracking_token'], name='campaigns_em_trackin_aa4a4e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailengagement',
            index=models.Index(fields=['campaign', 'recipient_email'], name='campaigns_em_campai_90cf67_idx'),
        ),
        migrations.AddIndex(
            model_name='emailengagement',
            index=models.Index(fields=['sent_at'], name='campaigns_em_sent_at_4dcf77_idx'),
        ),
    ]
