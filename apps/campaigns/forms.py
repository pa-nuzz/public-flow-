from django import forms
from .models import Campaign
from apps.senders.models import Sender

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'subject', 'from_name', 'reply_to', 'body_html', 'body_text', 'sender', 'scheduled_at']
        widgets = {
            'body_html': forms.Textarea(attrs={'rows': 10}),
            'body_text': forms.Textarea(attrs={'rows': 7}),
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = ['%Y-%m-%dT%H:%M']
        if user:
            self.fields['sender'].queryset = Sender.objects.filter(user=user, is_active=True)
