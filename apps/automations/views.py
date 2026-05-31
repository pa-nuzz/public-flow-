import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Workflow, WorkflowNode, WorkflowEdge, WorkflowEnrollment

logger = logging.getLogger(__name__)


@login_required
def workflow_list(request):
    workflows = Workflow.objects.filter(user=request.user).annotate(
        enrollment_count=Count('enrollments', filter=Q(enrollments__status='active')),
    )
    return render(request, 'automations/workflow_list.html', {
        'workflows': workflows,
    })


@login_required
def workflow_create(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Workflow name is required.')
            return render(request, 'automations/workflow_form.html')
        workflow = Workflow.objects.create(user=request.user, name=name)
        messages.success(request, f'Workflow "{name}" created.')
        return redirect('automations:workflow_edit', workflow_id=workflow.id)

    return render(request, 'automations/workflow_form.html')


@login_required
def workflow_edit(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, user=request.user)
    nodes = list(workflow.nodes.all().order_by('created_at'))
    edges = list(workflow.edges.all().order_by('created_at'))

    # Available email templates for action nodes
    from apps.campaigns.models import EmailTemplate
    from apps.contacts.models import ContactList

    templates = EmailTemplate.objects.filter(user=request.user, is_active=True)
    contact_lists = ContactList.objects.filter(user=request.user)

    return render(request, 'automations/workflow_form.html', {
        'workflow': workflow,
        'nodes_json': json.dumps([
            {'node_id': n.node_id, 'type': n.type, 'config': n.config}
            for n in nodes
        ]),
        'edges_json': json.dumps([
            {'from_node_id': e.from_node_id, 'to_node_id': e.to_node_id, 'condition': e.condition}
            for e in edges
        ]),
        'templates': templates,
        'contact_lists': contact_lists,
    })


@login_required
@require_POST
def workflow_delete(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, user=request.user)
    workflow.delete()
    messages.success(request, 'Workflow deleted.')
    return redirect('automations:workflow_list')


@login_required
@require_POST
def workflow_toggle(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, user=request.user)
    workflow.is_active = not workflow.is_active
    workflow.save(update_fields=['is_active', 'updated_at'])
    status = 'activated' if workflow.is_active else 'deactivated'
    messages.success(request, f'Workflow "{workflow.name}" {status}.')
    return redirect('automations:workflow_list')


@login_required
def workflow_analytics(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, user=request.user)
    enrollments = workflow.enrollments.all()
    active_count = enrollments.filter(status='active').count()
    completed_count = enrollments.filter(status='completed').count()

    return render(request, 'automations/workflow_analytics.html', {
        'workflow': workflow,
        'active_count': active_count,
        'completed_count': completed_count,
        'total_count': enrollments.count(),
    })


@login_required
@require_POST
def workflow_api_save_nodes(request):
    """Save the workflow node/edge graph from the flow builder."""
    try:
        data = json.loads(request.body)
        workflow_id = int(data.get('workflow_id', 0))
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])

        workflow = get_object_or_404(Workflow, id=workflow_id, user=request.user)

        # Clear existing nodes and edges
        workflow.nodes.all().delete()
        workflow.edges.all().delete()

        # Recreate nodes
        for n in nodes:
            WorkflowNode.objects.create(
                workflow=workflow,
                node_id=n.get('node_id'),
                type=n.get('type', 'action'),
                config=n.get('config', {}),
            )

        # Recreate edges
        for e in edges:
            WorkflowEdge.objects.create(
                workflow=workflow,
                from_node_id=e.get('from_node_id'),
                to_node_id=e.get('to_node_id'),
                condition=e.get('condition', 'default'),
            )

        return JsonResponse({'success': True})

    except Exception as exc:
        logger.error(f"Error saving workflow nodes: {exc}")
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
