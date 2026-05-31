import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def run_scheduled_campaigns_task():
    from .services import run_scheduled_campaigns
    run_scheduled_campaigns()


@shared_task(bind=True, max_retries=3)
def evaluate_ab_test_winner(self, campaign_id: int):
    """
    Evaluate A/B test variants after the test window expires.
    Picks the winner based on open rate, marks the campaign as completed,
    and stores the winning variant reference on the campaign.
    """
    try:
        from apps.campaigns.models import Campaign

        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except Campaign.DoesNotExist:
            logger.error(f"[A/B Task] Campaign {campaign_id} not found — aborting.")
            return

        if campaign.ab_test_status != 'running':
            logger.info(f"[A/B Task] Campaign {campaign_id} is not in running state ({campaign.ab_test_status}) — skipping.")
            return

        variants = list(campaign.variants.all().order_by('label'))
        if len(variants) < 2:
            logger.warning(f"[A/B Task] Campaign {campaign_id} has fewer than 2 variants — cannot evaluate.")
            return

        # Determine winner by open_rate (opens / sent)
        best_variant = max(variants, key=lambda v: v.open_rate)

        campaign.winner_variant = best_variant
        campaign.ab_test_status = 'completed'
        campaign.save(update_fields=['winner_variant', 'ab_test_status', 'updated_at'])

        logger.info(
            f"[A/B Task] Campaign {campaign_id}: Winner is Variant {best_variant.label} "
            f"with {best_variant.open_rate}% open rate (sent: {best_variant.sent_count}, opens: {best_variant.open_count})."
        )

    except Exception as exc:
        logger.error(f"[A/B Task] Error evaluating A/B winner for campaign {campaign_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
