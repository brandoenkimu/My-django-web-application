# admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from .models import Transaction, Profile, Wallet, KYCApplication, User
import csv
from django.contrib import admin
from .models import (
    Profile, KYCApplication, Wallet, Transaction, BalanceChange,
    SocialPost, SocialPostLike, SocialComment, FollowRelationship,
    Report, Notification, Subscriber
)
import json


def is_admin(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard with statistics"""

    # Get time periods
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # User statistics
    total_users = User.objects.count()
    new_users_today = User.objects.filter(date_joined__date=today).count()
    new_users_week = User.objects.filter(date_joined__date__gte=week_ago).count()
    active_users = User.objects.filter(last_login__date__gte=today - timedelta(days=1)).count()

    # Transaction statistics
    transactions = Transaction.objects.all()
    total_transactions = transactions.count()
    pending_transactions = transactions.filter(status__in=["PENDING", "PROCESSING"]).count()
    completed_transactions = transactions.filter(status="COMPLETED").count()
    failed_transactions = transactions.filter(status__in=["FAILED", "CANCELLED", "EXPIRED"]).count()

    # Amount statistics
    total_deposits = transactions.filter(txn_type="DEPOSIT", status="COMPLETED").aggregate(
        total=Sum('amount'))['total'] or 0
    total_withdrawals = transactions.filter(txn_type="WITHDRAW", status="COMPLETED").aggregate(
        total=Sum('amount'))['total'] or 0
    total_transfers = transactions.filter(txn_type="TRANSFER", status="COMPLETED").aggregate(
        total=Sum('amount'))['total'] or 0

    # KYC statistics
    kyc_applications = KYCApplication.objects.all()
    kyc_pending = kyc_applications.filter(status__in=["PENDING", "SUBMITTED"]).count()
    kyc_approved = kyc_applications.filter(status="APPROVED").count()
    kyc_rejected = kyc_applications.filter(status="REJECTED").count()

    # Recent transactions
    recent_transactions = transactions.order_by('-created_at')[:10]

    # Recent KYC applications
    recent_kyc = kyc_applications.order_by('-submitted_at')[:5]

    # Flagged transactions
    flagged_transactions = transactions.filter(is_flagged=True).count()

    # Pending withdrawals for approval
    pending_approvals = transactions.filter(
        txn_type__in=["WITHDRAW", "TRANSFER"],
        status__in=["PENDING", "PROCESSING"]
    ).count()

    context = {
        'total_users': total_users,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'active_users': active_users,

        'total_transactions': total_transactions,
        'pending_transactions': pending_transactions,
        'completed_transactions': completed_transactions,
        'failed_transactions': failed_transactions,

        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'total_transfers': total_transfers,

        'kyc_pending': kyc_pending,
        'kyc_approved': kyc_approved,
        'kyc_rejected': kyc_rejected,

        'flagged_transactions': flagged_transactions,
        'pending_approvals': pending_approvals,

        'recent_transactions': recent_transactions,
        'recent_kyc': recent_kyc,

        'today': today,
    }

    return render(request, 'admin/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def admin_transactions(request):
    """Admin transaction management"""

    # Get filter parameters
    txn_type = request.GET.get('type', 'all')
    status = request.GET.get('status', 'all')
    timeframe = request.GET.get('timeframe', 'all')
    search = request.GET.get('search', '')

    # Start with all transactions
    transactions = Transaction.objects.all().order_by('-created_at')

    # Apply filters
    if txn_type != 'all':
        transactions = transactions.filter(txn_type=txn_type)

    if status != 'all':
        transactions = transactions.filter(status=status)

    if timeframe != 'all':
        now = timezone.now()
        if timeframe == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'week':
            start_date = now - timedelta(days=7)
        elif timeframe == 'month':
            start_date = now - timedelta(days=30)
        elif timeframe == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None

        if start_date:
            transactions = transactions.filter(created_at__gte=start_date)

    if search:
        transactions = transactions.filter(
            Q(transaction_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(reference__icontains=search) |
            Q(description__icontains=search)
        )

    # Get statistics
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or 0
    total_count = transactions.count()

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(transactions, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'transactions': page_obj,
        'page_obj': page_obj,
        'total_amount': total_amount,
        'total_count': total_count,
        'current_filter': {
            'type': txn_type,
            'status': status,
            'timeframe': timeframe,
            'search': search,
        },
        'txn_types': Transaction.TXN_TYPES,
        'statuses': Transaction.TXN_STATUS,
    }

    return render(request, 'admin/transactions.html', context)


@login_required
@user_passes_test(is_admin)
def admin_transaction_detail(request, transaction_id):
    """Admin transaction detail view"""
    try:
        transaction = Transaction.objects.get(transaction_id=transaction_id)
    except Transaction.DoesNotExist:
        transaction = get_object_or_404(Transaction, pk=transaction_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            # Approve transaction
            if transaction.needs_admin_approval:
                transaction.approve_transaction(request.user)
                messages.success(request, f"Transaction {transaction.reference} approved successfully!")

                # Create audit log
                from .models import AdminAuditLog
                AdminAuditLog.objects.create(
                    admin=request.user,
                    action_type='TRANSACTION_APPROVE',
                    description=f"Approved transaction {transaction.reference} for {transaction.user.username}",
                    target_user=transaction.user,
                    target_object_id=str(transaction.transaction_id),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    metadata={
                        'amount': str(transaction.amount),
                        'currency': transaction.currency,
                        'type': transaction.txn_type
                    }
                )
            else:
                messages.error(request, "Transaction does not require approval")

        elif action == 'reject':
            # Reject transaction
            if transaction.needs_admin_approval:
                reason = request.POST.get('rejection_reason', 'No reason provided')
                transaction.reject_transaction(request.user, reason)
                messages.success(request, f"Transaction {transaction.reference} rejected!")

                # Create audit log
                from .models import AdminAuditLog
                AdminAuditLog.objects.create(
                    admin=request.user,
                    action_type='TRANSACTION_REJECT',
                    description=f"Rejected transaction {transaction.reference} for {transaction.user.username}",
                    target_user=transaction.user,
                    target_object_id=str(transaction.transaction_id),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    metadata={
                        'amount': str(transaction.amount),
                        'currency': transaction.currency,
                        'type': transaction.txn_type,
                        'reason': reason
                    }
                )
            else:
                messages.error(request, "Transaction does not require approval")

        elif action == 'update':
            # Update transaction details
            new_status = request.POST.get('status')
            admin_notes = request.POST.get('admin_notes')

            if new_status in [choice[0] for choice in Transaction.TXN_STATUS]:
                transaction.status = new_status
                transaction.admin_notes = admin_notes
                transaction.save()
                messages.success(request, "Transaction updated successfully!")

        elif action == 'flag':
            # Flag/unflag transaction
            is_flagged = request.POST.get('is_flagged') == 'true'
            flagged_reason = request.POST.get('flagged_reason', '')

            transaction.is_flagged = is_flagged
            if is_flagged:
                transaction.flagged_reason = flagged_reason
            else:
                transaction.flagged_reason = ''
            transaction.save()

            status = "flagged" if is_flagged else "unflagged"
            messages.success(request, f"Transaction {status} successfully!")

        return redirect('admin_transaction_detail', transaction_id=transaction_id)

    # Get user's transaction history
    user_transactions = Transaction.objects.filter(
        user=transaction.user
    ).order_by('-created_at')[:10]

    # Get user's KYC status
    try:
        kyc_status = transaction.user.kyc_application.status
    except:
        kyc_status = 'Not Submitted'

    context = {
        'transaction': transaction,
        'user_transactions': user_transactions,
        'kyc_status': kyc_status,
        'status_choices': Transaction.TXN_STATUS,
    }

    return render(request, 'admin/transaction_detail.html', context)


@login_required
@user_passes_test(is_admin)
def admin_users(request):
    """Admin user management"""

    search = request.GET.get('search', '')
    kyc_status = request.GET.get('kyc_status', 'all')

    users = User.objects.all().order_by('-date_joined')

    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    if kyc_status != 'all':
        if kyc_status == 'verified':
            users = users.filter(profile__kyc_verified=True)
        elif kyc_status == 'pending':
            users = users.filter(
                Q(kyc_application__status__in=["PENDING", "SUBMITTED"]) |
                Q(profile__kyc_verified=False)
            )
        elif kyc_status == 'rejected':
            users = users.filter(kyc_application__status="REJECTED")

    # Add profile and KYC data
    for user in users:
        try:
            user.profile_data = user.profile
        except:
            user.profile_data = None

        try:
            user.kyc_data = user.kyc_application
        except:
            user.kyc_data = None

        # Get wallet balance
        try:
            user.wallet_balance = user.wallet.balance
        except:
            user.wallet_balance = 0

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'current_filter': {
            'search': search,
            'kyc_status': kyc_status,
        },
    }

    return render(request, 'admin/users.html', context)


@login_required
@user_passes_test(is_admin)
def admin_user_detail(request, user_id):
    """Admin user detail view"""
    user = get_object_or_404(User, id=user_id)

    # Get or create profile
    profile, created = Profile.objects.get_or_create(user=user)

    # Get KYC if exists
    try:
        kyc = user.kyc_application
    except KYCApplication.DoesNotExist:
        kyc = None

    # Get wallet
    wallet, wallet_created = Wallet.objects.get_or_create(user=user)

    # Get user transactions
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:20]

    # Get recent balance changes
    balance_changes = user.balance_changes.all().order_by('-timestamp')[:10]

    if request.method == 'POST':
        # Update user balance
        if 'update_balance' in request.POST:
            try:
                adjustment = Decimal(request.POST.get('balance_adjustment', '0'))
                reason = request.POST.get('adjustment_reason', 'Admin adjustment')

                if adjustment != 0:
                    # Create admin modification transaction
                    Transaction.create_admin_modification(
                        user=user,
                        amount=adjustment,
                        description=reason,
                        admin_user=request.user
                    )

                    messages.success(request, f"Balance updated by ${adjustment:,.2f}")

            except (ValueError, InvalidOperation) as e:
                messages.error(request, f"Invalid adjustment amount: {str(e)}")

        # Update KYC status
        elif 'update_kyc' in request.POST and kyc:
            action = request.POST.get('kyc_action')

            if action == 'approve':
                kyc.approve(request.user, request.POST.get('admin_notes', ''))
                messages.success(request, "KYC approved successfully!")

            elif action == 'reject':
                kyc.reject(request.user, request.POST.get('rejection_reason', ''))
                messages.success(request, "KYC rejected!")

            elif action == 'request_revision':
                kyc.request_revision(request.user, request.POST.get('revision_notes', ''))
                messages.success(request, "Revision requested from user!")

        # Update user profile
        elif 'update_profile' in request.POST:
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            user.save()

            profile.plan = request.POST.get('plan', profile.plan)
            profile.phone = request.POST.get('phone', profile.phone)
            profile.country = request.POST.get('country', profile.country)
            profile.save()

            messages.success(request, "Profile updated successfully!")

    context = {
        'user_obj': user,
        'profile': profile,
        'kyc': kyc,
        'wallet': wallet,
        'transactions': transactions,
        'balance_changes': balance_changes,
        'plan_choices': Profile.PLAN_CHOICES,
    }

    return render(request, 'admin/user_detail.html', context)


@login_required
@user_passes_test(is_admin)
def admin_kyc(request):
    """Admin KYC management"""

    status = request.GET.get('status', 'pending')
    search = request.GET.get('search', '')

    kyc_list = KYCApplication.objects.all().order_by('-submitted_at')

    if status != 'all':
        kyc_list = kyc_list.filter(status=status)

    if search:
        kyc_list = kyc_list.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(full_name__icontains=search) |
            Q(document_number__icontains=search)
        )

    # Statistics
    total_kyc = kyc_list.count()
    pending_count = KYCApplication.objects.filter(status__in=["PENDING", "SUBMITTED"]).count()
    approved_count = KYCApplication.objects.filter(status="APPROVED").count()
    rejected_count = KYCApplication.objects.filter(status="REJECTED").count()

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(kyc_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'kyc_list': page_obj,
        'page_obj': page_obj,
        'total_kyc': total_kyc,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'current_filter': {
            'status': status,
            'search': search,
        },
        'status_choices': KYCApplication.STATUS_CHOICES,
    }

    return render(request, 'admin/kyc.html', context)


@login_required
@user_passes_test(is_admin)
def admin_kyc_detail(request, kyc_id):
    """Admin KYC detail view"""
    kyc = get_object_or_404(KYCApplication, id=kyc_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            notes = request.POST.get('admin_notes', '')
            kyc.approve(request.user, notes)
            messages.success(request, "KYC approved successfully!")

            # Create audit log
            from .models import AdminAuditLog
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type='KYC_APPROVE',
                description=f"Approved KYC for {kyc.user.username}",
                target_user=kyc.user,
                target_object_id=str(kyc.id),
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={
                    'document_type': kyc.document_type,
                    'document_number': kyc.document_number,
                    'country': kyc.country
                }
            )

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            kyc.reject(request.user, reason)
            messages.success(request, "KYC rejected!")

            # Create audit log
            from .models import AdminAuditLog
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type='KYC_REJECT',
                description=f"Rejected KYC for {kyc.user.username}",
                target_user=kyc.user,
                target_object_id=str(kyc.id),
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={
                    'document_type': kyc.document_type,
                    'document_number': kyc.document_number,
                    'country': kyc.country,
                    'reason': reason
                }
            )

        elif action == 'request_revision':
            notes = request.POST.get('revision_notes', '')
            kyc.request_revision(request.user, notes)
            messages.success(request, "Revision requested from user!")

        return redirect('admin_kyc_detail', kyc_id=kyc_id)

    # Get user's transactions for context
    user_transactions = Transaction.objects.filter(user=kyc.user).order_by('-created_at')[:10]

    context = {
        'kyc': kyc,
        'user_transactions': user_transactions,
        'document_types': KYCApplication.DOCUMENT_TYPES,
    }

    return render(request, 'admin/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def export_transactions_csv(request):
    """Export transactions to CSV"""
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)

    # Write CSV header
    writer.writerow([
        'Transaction ID', 'User', 'Type', 'Amount', 'Currency',
        'Status', 'Payment Method', 'Reference', 'Description',
        'Created At', 'Completed At', 'Balance Before', 'Balance After'
    ])

    # Get all transactions
    transactions = Transaction.objects.all().order_by('-created_at')

    # Write data rows
    for txn in transactions:
        writer.writerow([
            txn.transaction_id,
            txn.user.username,
            txn.get_txn_type_display(),
            txn.amount,
            txn.currency,
            txn.get_status_display(),
            txn.payment_method or '',
            txn.reference,
            txn.description or '',
            txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            txn.completed_at.strftime('%Y-%m-%d %H:%M:%S') if txn.completed_at else '',
            txn.balance_before or '',
            txn.balance_after or '',
        ])

    return response


@login_required
@user_passes_test(is_admin)
def api_transaction_stats(request):
    """API endpoint for transaction statistics"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Daily transaction counts for chart
    daily_data = []
    for i in range(7):
        date = week_ago + timedelta(days=i)
        count = Transaction.objects.filter(created_at__date=date).count()
        daily_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })

    # Transaction type distribution
    type_distribution = []
    for txn_type, display_name in Transaction.TXN_TYPES:
        count = Transaction.objects.filter(txn_type=txn_type).count()
        if count > 0:
            type_distribution.append({
                'type': display_name,
                'count': count
            })

    return JsonResponse({
        'daily_data': daily_data,
        'type_distribution': type_distribution,
    })




