from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.senders.models import Sender
from apps.campaigns.models import Campaign
from apps.senders.forms import SenderForm
from .forms import ProfileForm, ChangePasswordForm
from django.db.models import Sum, Avg
from django.utils import timezone

@login_required
def dashboard_view(request):
    user_campaigns = Campaign.objects.filter(user=request.user)
    senders = Sender.objects.filter(user=request.user, is_active=True)
    
    total_sent = user_campaigns.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    total_opens = user_campaigns.aggregate(Sum('open_count'))['open_count__sum'] or 0
    avg_open_rate = round((total_opens / total_sent * 100), 1) if total_sent > 0 else 0
    avg_spam_score = user_campaigns.filter(spam_score__isnull=False).aggregate(Avg('spam_score'))['spam_score__avg']
    
    recent_campaigns = user_campaigns.select_related('sender').order_by('-created_at')[:5]
    
    context = {
        'campaigns_count': user_campaigns.count(),
        'sent_count': total_sent,
        'avg_open_rate': avg_open_rate,
        'avg_spam_score': round(avg_spam_score, 1) if avg_spam_score else None,
        'senders_count': senders.count(),
        'recent_campaigns': recent_campaigns,
        'draft_count': user_campaigns.filter(status='draft').count(),
        'active_count': user_campaigns.filter(status__in=['sending', 'scheduled']).count(),
    }
    return render(request, "dashboard/home.html", context)

@login_required
def settings_view(request):
    senders = Sender.objects.filter(user=request.user)
    sender_form = SenderForm()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_sender':
            sender_form = SenderForm(request.POST)
            if sender_form.is_valid():
                sender = sender_form.save(commit=False)
                sender.user = request.user
                raw_password = sender_form.cleaned_data['smtp_password']
                sender.set_password(raw_password)
                sender.save()
                messages.success(request, 'Sender added successfully.')
                return redirect('dashboard:settings')
        elif action == 'delete_sender':
            sender_id = request.POST.get('sender_id')
            Sender.objects.filter(id=sender_id, user=request.user).delete()
            messages.success(request, 'Sender removed.')
            return redirect('dashboard:settings')
    
    context = {'senders': senders, 'sender_form': sender_form}
    return render(request, 'dashboard/settings.html', context)

@login_required
def profile_view(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = ChangePasswordForm(request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('dashboard:profile')
        elif action == 'change_password':
            password_form = ChangePasswordForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Password changed. Please log in again.')
                return redirect('accounts:login')
    
    return render(request, 'dashboard/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })

