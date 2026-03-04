from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.senders.models import *
from .models import *

# @login_required
def campaign_create(request):
    # Fetch data to populate the dropdown selects
    # senders = SMTPProfile.objects.filter(user=request.user, is_active=True)
    # lists = SubscriberList.objects.filter(user=request.user)

    if request.method == "POST":
        # logic to save the campaign (Draft) goes here
        # Dev A and B will collaborate here later to add Premailer logic
        pass

    context = {
        'senders': "senders",
        'lists': "lists"
    }
    return render(request, 'campaigns/campaigns_create.html', context)