import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
	'run-scheduled-campaigns-every-minute': {
		'task': 'apps.campaigns.tasks.run_scheduled_campaigns_task',
		'schedule': crontab(minute='*'),
	},
	'process-workflows-every-5-minutes': {
		'task': 'apps.automations.tasks.process_workflows_task',
		'schedule': crontab(minute='*/5'),
	},
}
