import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import Workflow, WorkflowEnrollment, WorkflowNode, WorkflowEdge

logger = logging.getLogger(__name__)


def process_workflow_enrollments():
    """
    Periodic processor that advances active enrollments whose next_execution_at
    has passed. Called by Celery beat or management command.
    """
    now = timezone.now()
    ready = WorkflowEnrollment.objects.filter(
        status='active',
        next_execution_at__lte=now,
    ).select_related('workflow', 'contact')

    processed = 0
    for enrollment in ready:
        try:
            _advance_enrollment(enrollment)
            processed += 1
        except Exception as exc:
            logger.error(
                f"Error advancing enrollment {enrollment.id} "
                f"(contact={enrollment.contact_id}, workflow={enrollment.workflow_id}): {exc}"
            )

    if processed:
        logger.info(f"Workflow engine processed {processed} enrollment(s).")
    return processed


def _advance_enrollment(enrollment):
    """Move an enrollment to the next node in its workflow graph."""
    workflow = enrollment.workflow
    current_node_id = enrollment.current_node_id

    # Determine next node
    if current_node_id is None:
        # Start at the first trigger node
        next_node = WorkflowNode.objects.filter(
            workflow=workflow,
            type='trigger',
        ).order_by('created_at').first()
    else:
        # Find the outgoing edge from the current node
        edge = WorkflowEdge.objects.filter(
            workflow=workflow,
            from_node_id=current_node_id,
        ).order_by('created_at').first()

        if edge is None:
            # No outgoing edge — enrollment is complete
            enrollment.status = 'completed'
            enrollment.current_node_id = None
            enrollment.next_execution_at = None
            enrollment.save()
            return

        next_node = WorkflowNode.objects.filter(
            workflow=workflow,
            node_id=edge.to_node_id,
        ).first()

    if next_node is None:
        enrollment.status = 'completed'
        enrollment.current_node_id = None
        enrollment.next_execution_at = None
        enrollment.save()
        return

    # Execute the node
    with transaction.atomic():
        enrollment.current_node_id = next_node.node_id

        if next_node.type == 'delay':
            hours = next_node.config.get('hours', 24)
            enrollment.next_execution_at = timezone.now() + timedelta(hours=hours)
        elif next_node.type == 'action':
            action_type = next_node.config.get('action', '')
            if action_type == 'send_email' and next_node.config.get('template_id'):
                _dispatch_template_email(enrollment, next_node.config['template_id'])
            elif action_type == 'add_tag' and next_node.config.get('tags'):
                _apply_tags(enrollment, next_node.config['tags'])
            elif action_type == 'remove_tag' and next_node.config.get('tags'):
                _remove_tags(enrollment, next_node.config['tags'])

            # After an action, immediately advance to the next node
            enrollment.next_execution_at = timezone.now()
        elif next_node.type == 'trigger':
            # Triggers just advance immediately
            enrollment.next_execution_at = timezone.now()

        enrollment.save()


def _dispatch_template_email(enrollment, template_id):
    """Dispatch a campaign email using the given template."""
    try:
        from apps.campaigns.models import EmailTemplate
        from apps.campaigns.services.delivery import send_campaign_with_smtp
        from apps.campaigns.models import Campaign
        from apps.senders.models import Sender

        sender = Sender.objects.filter(
            user=enrollment.workflow.user,
            is_active=True,
        ).first()
        if not sender:
            logger.warning(f"No active sender for workflow {enrollment.workflow_id}")
            return

        template = EmailTemplate.objects.filter(id=template_id).first()
        if not template:
            logger.warning(f"Template {template_id} not found")
            return

        campaign = Campaign.objects.create(
            user=enrollment.workflow.user,
            sender=sender,
            name=f"Automation: {enrollment.workflow.name}",
            subject=template.subject,
            body_text=template.body_text,
            body_html=template.body_html,
            recipient_emails=enrollment.contact.email,
            status='sending',
        )
        base_url = ''
        from django.conf import settings
        base_url = getattr(settings, 'PUBLIC_BASE_URL', 'http://localhost:8000')

        try:
            send_campaign_with_smtp(
                campaign,
                base_url,
                recipients_override=[enrollment.contact.email],
            )
        except Exception as exc:
            logger.error(f"Auto-dispatch failed for enrollment {enrollment.id}: {exc}")
            campaign.status = 'failed'
            campaign.save(update_fields=['status'])
    except Exception as exc:
        logger.error(f"Error dispatching template email: {exc}")


def _apply_tags(enrollment, tags):
    """Apply tags to the enrolled contact."""
    try:
        from apps.contacts.models import ContactTag
        contact = enrollment.contact
        for tag_name in tags:
            tag, _ = ContactTag.objects.get_or_create(
                user=enrollment.workflow.user,
                name=tag_name.strip(),
            )
            contact.tags.add(tag)
    except Exception as exc:
        logger.error(f"Error applying tags: {exc}")


def _remove_tags(enrollment, tags):
    """Remove tags from the enrolled contact."""
    try:
        from apps.contacts.models import ContactTag
        contact = enrollment.contact
        for tag_name in tags:
            tag = ContactTag.objects.filter(
                user=enrollment.workflow.user,
                name=tag_name.strip(),
            ).first()
            if tag:
                contact.tags.remove(tag)
    except Exception as exc:
        logger.error(f"Error removing tags: {exc}")


def enroll_contact(contact, workflow):
    """Enroll a contact in a workflow (called from signal or view)."""
    enrollment, created = WorkflowEnrollment.objects.get_or_create(
        contact=contact,
        workflow=workflow,
        defaults={
            'status': 'active',
            'next_execution_at': timezone.now(),
        }
    )
    if not created and enrollment.status != 'active':
        enrollment.status = 'active'
        enrollment.next_execution_at = timezone.now()
        enrollment.save()

    return enrollment
