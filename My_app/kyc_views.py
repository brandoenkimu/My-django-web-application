# kyc_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import KYCApplication, Profile
from .forms import KYCApplicationForm
import json


@login_required
def kyc_verification(request):
    """User KYC verification page"""

    # Check if user already has KYC
    try:
        kyc = request.user.kyc_application
        is_new = False
    except KYCApplication.DoesNotExist:
        kyc = None
        is_new = True

    # Check profile
    profile = request.user.profile

    if request.method == 'POST':
        if kyc and kyc.status == 'APPROVED':
            messages.info(request, "Your KYC is already approved!")
            return redirect('dashboard')

        form = KYCApplicationForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            kyc_app = form.save(commit=False)
            kyc_app.user = request.user

            # Add metadata
            kyc_app.ip_address = request.META.get('REMOTE_ADDR')
            kyc_app.user_agent = request.META.get('HTTP_USER_AGENT', '')

            # Set initial status
            if is_new:
                kyc_app.status = 'SUBMITTED'
                kyc_app.submitted_at = timezone.now()

            kyc_app.save()

            # Update profile submission time
            profile.kyc_submitted_at = timezone.now()
            profile.save()

            messages.success(request, "KYC application submitted successfully!")
            return redirect('kyc_status')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = KYCApplicationForm(instance=kyc)

    # Pre-fill form with profile data if available
    if is_new and not form.is_bound:
        form.initial.update({
            'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            'country': profile.country,
        })

    context = {
        'form': form,
        'kyc': kyc,
        'profile': profile,
        'is_new': is_new,
        'verification_progress': kyc.verification_progress if kyc else 0,
    }

    return render(request, 'kyc/verification.html', context)


@login_required
def kyc_status(request):
    """Check KYC application status"""
    try:
        kyc = request.user.kyc_application
    except KYCApplication.DoesNotExist:
        return redirect('kyc_verification')

    profile = request.user.profile

    context = {
        'kyc': kyc,
        'profile': profile,
        'verification_progress': kyc.verification_progress,
        'days_pending': kyc.days_since_submission,
    }

    return render(request, 'kyc/status.html', context)


@login_required
def kyc_resubmit(request):
    """Resubmit KYC after rejection"""
    try:
        kyc = request.user.kyc_application
        if kyc.status != 'REJECTED' and kyc.status != 'NEEDS_REVISION':
            messages.info(request, "Your KYC application doesn't need resubmission.")
            return redirect('kyc_status')
    except KYCApplication.DoesNotExist:
        messages.error(request, "No KYC application found.")
        return redirect('kyc_verification')

    if request.method == 'POST':
        form = KYCApplicationForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            kyc = form.save(commit=False)
            kyc.status = 'SUBMITTED'
            kyc.submitted_at = timezone.now()
            kyc.rejection_reason = ''  # Clear rejection reason
            kyc.revision_notes = ''  # Clear revision notes
            kyc.save()

            messages.success(request, "KYC application resubmitted successfully!")
            return redirect('kyc_status')
    else:
        form = KYCApplicationForm(instance=kyc)

    context = {
        'form': form,
        'kyc': kyc,
        'rejection_reason': kyc.rejection_reason,
        'revision_notes': kyc.revision_notes,
    }

    return render(request, 'kyc/resubmit.html', context)