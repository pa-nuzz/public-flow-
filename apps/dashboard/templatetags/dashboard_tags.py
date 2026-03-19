from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def greeting(context):
    hour = timezone.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"
