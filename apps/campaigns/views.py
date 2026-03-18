from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.senders.models import Sender
from .models import Campaign
from .forms import CampaignForm
from django.contrib import messages

# Create your views here.
@login_required
def campaign_create(request):
    senders = Sender.objects.filter(user=request.user, is_active=True)
    
    # if not senders.exists():
    #     messages.warning(request, 'Please add a sender before creating a campaign.')
    #     return redirect('dashboard:settings')
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, user=request.user)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.status = 'draft'
            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" saved as draft.')
            return redirect('dashboard:dashboard') # Detail view not implemented yet, using dashboard
    else:
        form = CampaignForm(user=request.user)
    
    return render(request, 'campaigns/create.html', {'form': form, 'senders': senders})


@login_required
def campaign_list(request):
    return render(request, "campaigns/list.html")