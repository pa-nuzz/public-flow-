from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.contacts.models import Contact, ContactList
from apps.automations.models import Workflow, WorkflowNode, WorkflowEdge, WorkflowEnrollment


class WorkflowModelTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
        )
        self.workflow = Workflow.objects.create(
            user=self.user,
            name='Test Workflow'
        )

    def test_workflow_creation(self):
        self.assertEqual(self.workflow.name, 'Test Workflow')
        self.assertTrue(self.workflow.is_active)

    def test_workflow_node_creation(self):
        node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='trigger_1',
            type='trigger',
            config={'event': 'list_signup'}
        )
        self.assertEqual(node.type, 'trigger')
        self.assertEqual(node.config['event'], 'list_signup')

    def test_workflow_edge_creation(self):
        node_a = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node_a',
            type='trigger',
        )
        node_b = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node_b',
            type='delay',
            config={'hours': 24}
        )
        edge = WorkflowEdge.objects.create(
            workflow=self.workflow,
            from_node_id=node_a.node_id,
            to_node_id=node_b.node_id,
        )
        self.assertEqual(edge.from_node_id, 'node_a')
        self.assertEqual(edge.to_node_id, 'node_b')

    def test_enrollment_state_transition(self):
        contact_list = ContactList.objects.create(
            user=self.user,
            name='Test List'
        )
        contact = Contact.objects.create(
            contact_list=contact_list,
            email='test@example.com',
            is_active=True
        )
        enrollment = WorkflowEnrollment.objects.create(
            contact=contact,
            workflow=self.workflow,
            status='active'
        )
        self.assertEqual(enrollment.status, 'active')

        enrollment.status = 'completed'
        enrollment.save()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, 'completed')

    def test_enrollment_next_execution(self):
        contact_list = ContactList.objects.create(
            user=self.user,
            name='Test List'
        )
        contact = Contact.objects.create(
            contact_list=contact_list,
            email='test2@example.com',
            is_active=True
        )
        future = timezone.now() + timedelta(hours=2)
        enrollment = WorkflowEnrollment.objects.create(
            contact=contact,
            workflow=self.workflow,
            status='active',
            next_execution_at=future
        )
        self.assertIsNotNone(enrollment.next_execution_at)
        self.assertTrue(enrollment.next_execution_at > timezone.now())
