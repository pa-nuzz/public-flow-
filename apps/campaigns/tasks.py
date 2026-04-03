from celery import shared_task

from .services import run_scheduled_campaigns


@shared_task(name='apps.campaigns.tasks.run_scheduled_campaigns_task')
def run_scheduled_campaigns_task():
    return run_scheduled_campaigns()
