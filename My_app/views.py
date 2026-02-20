from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Sum, Count
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal
import json
import time
import uuid
import random
import requests
import stripe
import os
# My_app/views.py - CORRECTED IMPORTS
from .models import (
    SocialPost,  # This is your Post model
    SocialComment,  # This is your Comment model
    SocialPostLike,  # This is your Like model
    FollowRelationship,  # This is your Follow model
    ChatMessage,  # This is your Message model
    ChatRoom,  # This is your MessageRoom model
    Notification,
    Profile,
    Wallet,
    Transaction,
    Report,
    Subscriber
)

# For convenience, you can create aliases
Post = SocialPost
Comment = SocialComment
Like = SocialPostLike
Follow = FollowRelationship
Message = ChatMessage
MessageRoom = ChatRoom

# Models and Forms
from .forms import KYCForm, DepositForm, WithdrawForm, ProfileUpdateForm, UserUpdateForm, SubscriberForm
from .models import KYCApplication, Transaction, Wallet, Profile

# Django messages with aliases to avoid conflicts
from django.contrib.messages import success as msg_success
from django.contrib.messages import error as msg_error
from django.contrib.messages import warning as msg_warning
from django.contrib.messages import info as msg_info

# Rest Framework imports
from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import KYCSerializer, TransactionSerializer

# Stripe setup
if hasattr(settings, "STRIPE_SECRET_KEY"):
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ==================== REST API VIEWSETS ====================
class KYCViewSet(viewsets.ModelViewSet):
    serializer_class = KYCSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KYCApplication.objects.filter(user=self.request.user).order_by("-submitted_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        ref_prefix = "DEP" if serializer.validated_data.get("txn_type", "DEPOSIT") == "DEPOSIT" else "WDR"
        serializer.save(user=self.request.user, reference=f"{ref_prefix}-{uuid.uuid4().hex[:12]}")


@api_view(["GET"])
def transaction_updates(request):
    txns = Transaction.objects.filter(user=request.user).order_by("-created_at")[:10]
    return Response(TransactionSerializer(txns, many=True).data)


# ==================== BASIC PAGES ====================
def index(request):
    return render(request, 'polls/base.html')


def about(request):
    return render(request, 'polls/about.html')


def contact(request):
    return render(request, 'polls/contact.html')


def user(request):
    return render(request, 'polls/user.html')


def privacy_policy(request):
    return render(request, 'polls/privacy_policy.html', {})


def terms_of_service(request):
    return render(request, 'polls/terms_of_service.html', {})


def contact1(request):
    return render(request, 'polls/contact1.html', {})


def risk_disclosure(request):
    return render(request, 'polls/risk_disclosure.html', {})


def new_year_view(request):
    current_year = datetime.now().year
    username = request.user.username if request.user.is_authenticated else "Trader"
    return render(request, "polls/new_year.html", {
        "current_year": current_year,
        "target_year": 2026,
        "username": username
    })


def subscribe_view(request):
    if request.method == "POST":
        form = SubscriberForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))


# ==================== AUTHENTICATION VIEWS ====================
def signup_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        msg_info(request, f"👋 Welcome back, {request.user.username}!")
        return redirect('base')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        # Basic validation
        validation_issues = []
        if not username: validation_issues.append("Username is required")
        if not email: validation_issues.append("Email address is required")
        if not password1: validation_issues.append("Password is required")
        if not password2: validation_issues.append("Confirm password is required")

        if validation_issues:
            msg_error(request, f"Missing Information: {' • '.join(validation_issues)}")
            return render(request, 'polls/signup.html')

        if password1 != password2:
            msg_error(request, "Passwords do not match")
            return render(request, 'polls/signup.html')

        if User.objects.filter(username=username).exists():
            msg_error(request, f"Username '{username}' is already taken")
            return render(request, 'polls/signup.html')

        if User.objects.filter(email=email).exists():
            msg_error(request, f"Email '{email}' is already registered")
            return render(request, 'polls/signup.html')

        if len(password1) < 6:
            msg_warning(request, "Password must be at least 6 characters")
            return render(request, 'polls/signup.html')

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )

            # Store success data in session
            request.session['registration_success'] = True
            request.session['registered_username'] = username
            request.session['registered_email'] = email
            request.session['account_id'] = f"TRD{user.id:06d}"

            return redirect('registration_success')

        except Exception as e:
            msg_error(request, f"Registration failed: {str(e)}")

    return render(request, 'polls/signup.html')


def registration_success_view(request):
    """Show success message after registration"""
    if not request.session.get('registration_success', False):
        msg_error(request, "No registration in progress")
        return redirect('signup')

    username = request.session.get('registered_username', '')
    email = request.session.get('registered_email', '')
    account_id = request.session.get('account_id', '')

    # Clear session data
    for key in ['registration_success', 'registered_username', 'registered_email', 'account_id']:
        request.session.pop(key, None)

    return render(request, 'polls/registration_success.html', {
        'username': username,
        'email': email,
        'account_id': account_id,
        'login_url': reverse('login')
    })


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('base')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            msg_success(request, f"Welcome back, {user.username}!")
            return redirect('base')
        else:
            msg_error(request, "Invalid username or password")

    return render(request, 'polls/login.html')


def logout_view(request):
    logout(request)
    return redirect("login")


def admin_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('/admin/')
        msg_error(request, "Invalid credentials or not an admin")
    return render(request, "polls/admin_login.html")


def home_redirect(request):
    """Redirect to signup if not logged in, otherwise to dashboard"""
    if request.user.is_authenticated:
        return redirect('base')
    else:
        return redirect('signup')


def check_username(request):
    """AJAX endpoint to check username availability"""
    username = request.GET.get('username', '').strip()

    if not username:
        return JsonResponse({'available': False, 'message': 'Username is required'})

    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Username too short (min 3 characters)'})

    exists = User.objects.filter(username=username).exists()

    return JsonResponse({
        'available': not exists,
        'message': 'Username is available' if not exists else 'Username already taken'
    })


# ==================== PROFILE & SETTINGS ====================
@login_required
def profile_view(request):
    """Profile update view with picture upload support"""

    if request.method == 'POST':
        # Profile picture update
        if 'update_picture' in request.POST:
            if 'profile_picture' in request.FILES and request.FILES['profile_picture']:
                profile_pic = request.FILES['profile_picture']

                # Validate file size (5MB max)
                if profile_pic.size > 5 * 1024 * 1024:
                    msg_error(request, 'File size must be under 5MB')
                else:
                    # Validate file type
                    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                    if profile_pic.content_type not in allowed_types:
                        msg_error(request, 'File must be JPG, PNG, GIF or WebP')
                    else:
                        # Save the picture
                        profile = request.user.profile
                        profile.profile_picture = profile_pic
                        profile.save()
                        msg_success(request, 'Profile picture updated successfully!')
            else:
                msg_error(request, 'No image selected')

            return redirect('profile')

        # Regular profile update
        elif 'update_profile' in request.POST:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            country = request.POST.get('country', '').strip()
            phone = request.POST.get('phone', '').strip()
            bio = request.POST.get('bio', '').strip()[:500]

            # Update user
            user = request.user
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Update profile
            profile = request.user.profile
            profile.country = country
            profile.phone = phone
            profile.bio = bio
            profile.save()

            msg_success(request, 'Profile updated successfully!')
            return redirect('profile')

        else:
            msg_error(request, 'Invalid form submission')

    # For GET request
    context = {
        'profile_form': None,
        'profile': request.user.profile,
    }

    return render(request, 'polls/profile.html', context)


@login_required
def settings_view(request):
    """Simplified settings update view"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        country = request.POST.get('country', '').strip()
        phone = request.POST.get('phone', '').strip()
        bio = request.POST.get('bio', '').strip()

        # Update user
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # Update profile
        profile = request.user.profile
        profile.country = country
        profile.phone = phone
        profile.bio = bio
        profile.save()

        msg_success(request, 'Settings updated successfully!')
        return redirect('settings')

    return render(request, 'polls/settings.html')


@login_required
def user_dashboard(request):
    return render(request, 'polls/user.html')


@login_required(login_url="login")
def base_view(request):
    return render(request, "polls/base.html")


@login_required(login_url="login")
def dashboard(request):
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileUpdateForm(instance=request.user.profile)

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect("dashboard")

    return render(request, "polls/base.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })


# ==================== TRADING PAGES ====================
# Strategy Development pages
def strategy_lab(request):
    return render(request, 'polls/strategy_lab.html')


def advanced_trading_tools(request):
    return render(request, 'polls/advanced_trading_tools.html')


def algo_trading_platform(request):
    return render(request, 'polls/algo_trading_platform.html')


def trade_builder(request):
    return render(request, 'polls/trade_builder.html')


def market_blueprint(request):
    return render(request, 'polls/market_blueprint.html')


def charting_suite(request):
    return render(request, 'polls/charting_suite.html')


def indicator_workshop(request):
    return render(request, 'polls/indicator_workshop.html')


def trading_toolkit(request):
    return render(request, 'polls/trading_toolkit.html')


def backtest_center(request):
    return render(request, 'polls/backtest_center.html')


def trade_development(request):
    return render(request, 'polls/trade_development.html')


def market_research(request):
    return render(request, 'polls/market_research.html')


# Live Trading pages
def execution_hub(request):
    return render(request, 'polls/execution_hub.html')


def live_trading(request):
    return render(request, 'polls/live_trading.html')


def trade_operations(request):
    return render(request, 'polls/trade_operations.html')


def market_monitor(request):
    return render(request, 'polls/market_monitor.html')


def sentiment_watch(request):
    return render(request, 'polls/sentiment_watch.html')


def automation_center(request):
    return render(request, 'polls/automation_center.html')


def risk_console(request):
    return render(request, 'polls/risk_console.html')


def performance_tracker(request):
    return render(request, 'polls/performance_tracker.html')


def signal_runner(request):
    return render(request, 'polls/signal_runner.html')


def trade_manager(request):
    return render(request, 'polls/trade_manager.html')


def position_control(request):
    return render(request, 'polls/position_control.html')


def trading_chart(request):
    return render(request, "market_research.html")


def market_research_view(request):
    return render(request, "market_research.html")


# ==================== KYC & TRANSACTIONS ====================
@login_required
def kyc_apply(request):
    if request.method == "POST":
        form = KYCForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect("transactions")
    else:
        form = KYCForm()
    apps = KYCApplication.objects.filter(user=request.user).order_by("-submitted_at")
    return render(request, "polls/kyc.html", {"form": form, "kyc_apps": apps})


@login_required
def withdraw(request):
    if request.method == "POST":
        form = WithdrawForm(request.POST)
        if form.is_valid():
            form.save(user=request.user)
            return redirect("transactions")
    else:
        form = WithdrawForm()
    return render(request, "polls/withdraw.html", {"form": form})


@login_required
def transactions_view(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'polls/transactions.html', {'transactions': transactions})


@login_required
def live_transactions(request):
    """API endpoint for live transaction updates"""
    last_update = request.GET.get('last_update', None)

    if last_update:
        new_transactions = Transaction.objects.filter(
            user=request.user,
            created_at__gt=last_update
        ).order_by('-created_at')
    else:
        new_transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]

    transactions_data = []
    for txn in new_transactions:
        transactions_data.append({
            'reference': txn.reference,
            'txn_type': txn.txn_type,
            'amount': str(txn.amount),
            'currency': txn.currency,
            'status': txn.status,
            'created_at': txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'id': txn.id
        })

    return JsonResponse({
        'transactions': transactions_data,
        'last_update': datetime.now().isoformat() if new_transactions.exists() else last_update
    })


# Alias for URL compatibility
api_live_transactions = live_transactions


@csrf_exempt
@login_required
def create_transaction(request):
    """Create a new transaction (for deposit/withdraw)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            txn = Transaction.objects.create(
                user=request.user,
                reference=data.get('reference', f"TXN-{int(time.time())}"),
                txn_type=data.get('type', 'DEPOSIT'),
                amount=data.get('amount', 0),
                currency=data.get('currency', 'USD'),
                status='PENDING'
            )
            return JsonResponse({'success': True, 'transaction_id': txn.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


@login_required
def ajax_deposit(request):
    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            txn = form.save(user=request.user)
            return JsonResponse({"success": True, "reference": txn.reference})
    return JsonResponse({"success": False})


@login_required
def ajax_withdraw(request):
    if request.method == "POST":
        form = WithdrawForm(request.POST)
        if form.is_valid():
            txn = form.save(user=request.user)
            return JsonResponse({"success": True, "reference": txn.reference})
    return JsonResponse({"success": False})



@login_required
def process_deposit(request):
    """Alias for deposit_funds"""
    return deposit_funds(request)


@login_required
def transaction_status(request, transaction_id):
    """Show transaction status page"""
    try:
        transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
    except Transaction.DoesNotExist:
        msg_error(request, "Transaction not found")
        return redirect('transactions')

    return render(request, "polls/transaction_status.html", {'transaction': transaction})


# My_app/views.py (add this to existing views)
@login_required
def transactions(request):
    """Main transactions page view"""
    # Get user's transactions
    user_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

    # Pagination
    paginator = Paginator(user_transactions, 20)  # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate stats
    completed_count = user_transactions.filter(status='COMPLETED').count()
    pending_count = user_transactions.filter(status__in=['PENDING', 'PROCESSING']).count()
    failed_count = user_transactions.filter(status__in=['FAILED', 'EXPIRED', 'CANCELLED']).count()

    # Total amount (completed transactions only)
    total_amount = user_transactions.filter(status='COMPLETED').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Success rate
    total_txns = user_transactions.count()
    success_rate = (completed_count / total_txns * 100) if total_txns > 0 else 0

    context = {
        'transactions': page_obj,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'failed_count': failed_count,
        'total_amount': total_amount,
        'success_rate': round(success_rate, 1),
        'total_count': total_txns,
    }

    return render(request, 'polls/transactions.html', context)

@login_required
def transaction_history(request):
    """Alias for transactions view"""
    return transactions(request)


# ==================== PAYMENT CALLBACKS ====================
@csrf_exempt
@require_POST
def mpesa_callback(request):
    """M-Pesa payment callback"""
    try:
        data = json.loads(request.body)

        if 'Body' in data and 'stkCallback' in data['Body']:
            callback = data['Body']['stkCallback']
            checkout_request_id = callback.get('CheckoutRequestID')
            result_code = callback.get('ResultCode')

            if result_code == 0:
                try:
                    transaction = Transaction.objects.get(
                        gateway_transaction_id=checkout_request_id,
                        status='PENDING'
                    )
                    transaction.status = 'COMPLETED'
                    if transaction.metadata:
                        transaction.metadata['mpesa_callback'] = callback
                    else:
                        transaction.metadata = {'mpesa_callback': callback}
                    transaction.save()

                    # Update wallet
                    try:
                        wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                        wallet.balance += transaction.amount
                        wallet.save()
                    except:
                        pass

                except Transaction.DoesNotExist:
                    pass

                return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Callback received"})

    except Exception as e:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Error"})


@login_required
def paypal_success(request):
    """PayPal success callback"""
    transaction_id = request.GET.get('transaction_id')
    payment_id = request.GET.get('paymentId')
    payer_id = request.GET.get('PayerID')

    if transaction_id:
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'COMPLETED'
            transaction.gateway_transaction_id = payment_id or payer_id
            transaction.save()

            try:
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.balance += transaction.amount
                wallet.save()
            except:
                pass

            msg_success(request, 'PayPal payment completed successfully!')
        except Transaction.DoesNotExist:
            msg_error(request, 'Transaction not found')

    return redirect('transactions')


@login_required
def paypal_cancel(request):
    """PayPal cancellation callback"""
    transaction_id = request.GET.get('transaction_id')

    if transaction_id:
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'CANCELLED'
            transaction.save()
            msg_warning(request, 'PayPal payment was cancelled.')
        except Transaction.DoesNotExist:
            pass

    return redirect('deposit')


@login_required
def alipay_callback(request):
    """Alipay callback"""
    transaction_id = request.GET.get('transaction_id')
    trade_status = request.GET.get('trade_status')

    if transaction_id and trade_status == 'TRADE_SUCCESS':
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'COMPLETED'
            transaction.save()

            try:
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.balance += transaction.amount
                wallet.save()
            except:
                pass

            msg_success(request, 'Alipay payment completed successfully!')
        except Transaction.DoesNotExist:
            msg_error(request, 'Transaction not found')

    return redirect('deposit')


@csrf_exempt
def stripe_webhook(request):
    """Stripe webhook handler"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event_type = data.get('type')

            if event_type == 'payment_intent.succeeded':
                payment_intent = data.get('data', {}).get('object', {})
                payment_intent_id = payment_intent.get('id')

                if payment_intent_id:
                    try:
                        transaction = Transaction.objects.get(
                            gateway_transaction_id=payment_intent_id,
                            status='PENDING'
                        )
                        transaction.status = 'COMPLETED'
                        transaction.save()

                        try:
                            wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                            wallet.balance += transaction.amount
                            wallet.save()
                        except:
                            pass

                    except Transaction.DoesNotExist:
                        pass

            return JsonResponse({'status': 'success'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return HttpResponse(status=400)


# ==================== WALLET & UTILITIES ====================
@login_required
def wallet_balance(request):
    """Get user wallet balance"""
    try:
        wallet = Wallet.objects.get(user=request.user)
        balance = wallet.balance
        currency = wallet.currency
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(user=request.user)
        balance = 0
        currency = 'USD'

    return JsonResponse({
        'balance': float(balance),
        'currency': currency,
        'user': request.user.username
    })


@login_required
def retry_transaction(request, transaction_id):
    """Retry a failed transaction"""
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

    if transaction.status in ['FAILED', 'CANCELLED']:
        new_transaction = Transaction.objects.create(
            user=request.user,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.currency,
            payment_method=transaction.payment_method,
            status='PENDING',
            metadata={'retry_of': str(transaction.transaction_id)}
        )

        msg_success(request, 'Transaction retry initiated!')
        return redirect('transactions')

    msg_error(request, 'Cannot retry this transaction')
    return redirect('transactions')


# ==================== API ENDPOINTS ====================
@login_required
def api_live_transactions_view(request):
    """API endpoint for live transaction updates"""
    last_update = request.GET.get('last_update')

    try:
        if last_update:
            try:
                last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                new_transactions = Transaction.objects.filter(
                    user=request.user,
                    updated_at__gt=last_update_dt
                ).order_by('-created_at')[:20]
            except:
                new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:20]
        else:
            new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:20]

        transactions_data = []
        for txn in new_transactions:
            transactions_data.append({
                'id': txn.id,
                'transaction_id': str(txn.transaction_id),
                'amount': float(txn.amount),
                'currency': txn.currency,
                'payment_method': txn.payment_method,
                'payment_reference': txn.payment_reference or '',
                'status': txn.status.lower(),
                'metadata': txn.metadata if txn.metadata else {},
                'created_at': txn.created_at.isoformat(),
                'updated_at': txn.updated_at.isoformat(),
            })

        total_deposits = Transaction.objects.filter(
            user=request.user,
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).count()

        total_amount_result = Transaction.objects.filter(
            user=request.user,
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))

        total_amount = str(total_amount_result['total'] or '0')

        return JsonResponse({
            'success': True,
            'transactions': transactions_data,
            'last_update': timezone.now().isoformat(),
            'stats': {
                'total_deposits': total_deposits,
                'total_amount': total_amount,
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'transactions': [],
            'last_update': timezone.now().isoformat()
        })


@login_required
def api_transaction_details(request, transaction_id):
    """API endpoint for transaction details"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user
        )
        return JsonResponse({
            'success': True,
            'transaction': {
                'transaction_id': str(transaction.transaction_id),
                'amount': float(transaction.amount),
                'currency': transaction.currency,
                'payment_method': transaction.payment_method,
                'payment_reference': transaction.payment_reference,
                'status': transaction.status.lower(),
                'metadata': transaction.metadata if transaction.metadata else {},
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'user_email': request.user.email,
            }
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transaction not found'})


@login_required
@require_POST
def api_retry_transaction(request, transaction_id):
    """API endpoint to retry a failed transaction"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user,
            status='FAILED'
        )

        new_transaction_id = f"RETRY{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

        new_transaction = Transaction.objects.create(
            user=request.user,
            transaction_id=new_transaction_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.currency,
            status='PENDING',
            payment_method=transaction.payment_method,
            payment_reference=f"RETRY{int(time.time())}",
            metadata=transaction.metadata if transaction.metadata else {}
        )

        return JsonResponse({
            'success': True,
            'message': 'Retry initiated',
            'new_transaction_id': new_transaction.transaction_id
        })

    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found or cannot be retried'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def api_transactions_list(request):
    """API endpoint for transactions list"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]

    data = {
        'transactions': [
            {
                'id': str(txn.transaction_id),
                'reference': txn.payment_reference or '',
                'type': txn.transaction_type,
                'amount': float(txn.amount),
                'currency': txn.currency,
                'payment_method': txn.payment_method,
                'status': txn.status,
                'created_at': txn.created_at.isoformat(),
                'formatted_amount': f"{txn.currency} {txn.amount:.2f}",
            }
            for txn in transactions
        ]
    }

    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
def verify_payment(request):
    """Verify payment status"""
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if transaction_id:
            try:
                transaction = Transaction.objects.get(transaction_id=transaction_id)
                return JsonResponse({
                    'success': True,
                    'status': transaction.status,
                    'amount': float(transaction.amount),
                    'currency': transaction.currency
                })
            except Transaction.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Transaction not found'
                }, status=404)

        return JsonResponse({
            'success': False,
            'error': 'Transaction ID required'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== ADMIN VIEWS ====================
@staff_member_required
def kyc_admin_panel(request):
    kyc_list = KYCApplication.objects.filter(status="PENDING")
    return render(request, "admin_kyc.html", {"kyc_list": kyc_list})


@staff_member_required
def approve_kyc(request, kyc_id):
    kyc = KYCApplication.objects.get(id=kyc_id)
    kyc.status = "APPROVED"
    kyc.save()
    return redirect("kyc_admin")


# ==================== MARKET DATA ====================
def get_realtime_price(request, symbol):
    """API endpoint to get real-time price data from TwelveData"""
    API_KEY = settings.TWELVE_DATA_API_KEY

    symbol_map = {
        'FX:EURUSD': 'EUR/USD',
        'FX:GBPUSD': 'GBP/USD',
        'FX:USDJPY': 'USD/JPY',
        'FX:USDCHF': 'USD/CHF',
        'FX:USDCAD': 'USD/CAD',
        'FX:AUDUSD': 'AUD/USD',
        'FX:NZDUSD': 'NZD/USD',
        'FX:EURGBP': 'EUR/GBP',
        'FX:EURJPY': 'EUR/JPY',
        'FX:GBPJPY': 'GBP/JPY',
        'FX:EURCHF': 'EUR/CHF',
        'FX:AUDJPY': 'AUD/JPY',
        'FX:CADJPY': 'CAD/JPY',
        'OANDA:XAUUSD': 'XAU/USD',
        'OANDA:XAGUSD': 'XAG/USD',
        'NASDAQ:AAPL': 'AAPL',
        'NASDAQ:TSLA': 'TSLA',
        'NASDAQ:MSFT': 'MSFT',
        'NASDAQ:GOOGL': 'GOOGL',
        'NASDAQ:AMZN': 'AMZN',
        'NASDAQ:META': 'META',
        'NASDAQ:NVDA': 'NVDA',
        'AMEX:SPY': 'SPY',
        'NASDAQ:QQQ': 'QQQ',
        'NYSE:IBM': 'IBM',
        'NYSE:JPM': 'JPM',
        'BINANCE:BTCUSDT': 'BTC/USDT',
        'BINANCE:ETHUSDT': 'ETH/USDT',
        'BINANCE:ADAUSDT': 'ADA/USDT',
        'BINANCE:DOTUSDT': 'DOT/USDT',
        'BINANCE:BNBUSDT': 'BNB/USDT',
        'BINANCE:XRPUSDT': 'XRP/USDT',
        'BINANCE:SOLUSDT': 'SOL/USDT',
        'BINANCE:DOGEUSDT': 'DOGE/USDT',
        'BINANCE:MATICUSDT': 'MATIC/USDT',
        'BINANCE:AVAXUSDT': 'AVAX/USDT',
        'CME_MINI:ES1!': 'ES',
        'CME_MINI:NQ1!': 'NQ',
        'CBOT_MINI:YM1!': 'YM',
        'COMEX:GC1!': 'GC',
        'COMEX:SI1!': 'SI',
        'NYMEX:CL1!': 'CL',
        'NYMEX:NG1!': 'NG',
        'SP:SPX': 'SPX',
        'DJ:DJI': 'DJI',
        'NASDAQ:NDX': 'NDX',
        'RUSSELL:RUT': 'RUT',
        'FTSE:UKX': 'UKX',
        'INDEX:DAX': 'DAX',
        'INDEX:CAC': 'CAC',
        'INDEX:NI225': 'NI225'
    }

    td_symbol = symbol_map.get(symbol, symbol)
    url = f"https://api.twelvedata.com/quote?symbol={td_symbol}&apikey={API_KEY}"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if "code" in data and data["code"] != 200:
            return JsonResponse({"error": data.get("message", "Invalid symbol")}, status=400)

        return JsonResponse({
            "symbol": symbol,
            "price": data.get("close") or data.get("price"),
            "percent_change": data.get("percent_change"),
            "change": data.get("change"),
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "volume": data.get("volume"),
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_price(request, symbol):
    API_KEY = "b0e7b04c7af942f7883ede7d5cce7459"

    try:
        provider_symbol = symbol.split(":")[-1]
        url = "https://api.twelvedata.com/quote"
        r = requests.get(url, params={"symbol": provider_symbol, "apikey": API_KEY}, timeout=5)
        data = r.json()

        if data.get("status") == "error":
            return JsonResponse({"error": data.get("message", "API error")}, status=400)

        return JsonResponse({
            "symbol": symbol,
            "price": data.get("price"),
            "change": data.get("change"),
            "percent_change": data.get("percent_change"),
            "high": data.get("high"),
            "low": data.get("low"),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ==================== STRIPE PAYMENTS ====================
def create_stripe_session(request):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'Deposit'},
                    'unit_amount': 1000,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='http://localhost:8000/success/',
            cancel_url='http://localhost:8000/cancel/',
        )
        return JsonResponse({"id": session.id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def billing_view(request):
    customer = stripe.Customer.list(email=request.user.email, limit=1)
    customer = customer.data[0] if customer.data else None
    return render(request, "polls/billing.html", {"customer": customer})


# ==================== SOCIAL LOGIN ====================
def google_login(request):
    return redirect('/accounts/google/login/')


def google_callback(request):
    return redirect('home')


def facebook_login(request):
    return redirect('/accounts/facebook/login/')


def facebook_callback(request):
    return redirect('home')


def telegram_login(request):
    msg_info(request, "Telegram login coming soon! Please use email signup for now.")
    return redirect('signup')


def telegram_callback(request):
    msg_info(request, "Telegram authentication is not fully implemented yet.")
    return redirect('signup')


def instagram_login(request):
    client_id = "YOUR_INSTAGRAM_CLIENT_ID"
    redirect_uri = request.build_absolute_uri('/auth/instagram/callback/')
    auth_url = f"https://api.instagram.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=user_profile&response_type=code"
    return redirect(auth_url)


def instagram_callback(request):
    code = request.GET.get('code')

    if code:
        try:
            client_id = "YOUR_INSTAGRAM_CLIENT_ID"
            client_secret = "YOUR_INSTAGRAM_CLIENT_SECRET"
            redirect_uri = request.build_absolute_uri('/auth/instagram/callback/')

            token_url = "https://api.instagram.com/oauth/access_token"
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code': code
            }

            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                user_id = token_data.get('user_id')

                user_url = f"https://graph.instagram.com/{user_id}"
                params = {
                    'fields': 'id,username',
                    'access_token': token_data.get('access_token')
                }
                user_response = requests.get(user_url, params=params)

                if user_response.status_code == 200:
                    user_data = user_response.json()
                    username = user_data.get('username')

                    user, created = User.objects.get_or_create(
                        username=f"instagram_{username}",
                        defaults={'email': f"{username}@instagram.com"}
                    )

                    login(request, user)
                    msg_success(request, f"Logged in with Instagram as {username}!")
                    return redirect('home')

        except Exception as e:
            msg_error(request, f"Instagram login error: {str(e)}")

    msg_error(request, "Instagram login failed. Please try another method.")
    return redirect('signup')


# ==================== MESSAGING SYSTEM ====================
# Sample data classes
class Message:
    def __init__(self, id, sender, subject, body, timestamp, folder='inbox', read=False):
        self.id = id
        self.sender = sender
        self.subject = subject
        self.body = body
        self.timestamp = timestamp
        self.folder = folder
        self.read = read


class Notification:
    def __init__(self, id, title, description, status, date):
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.date = date


# Sample data
sample_messages = [
    Message(1, "Customer Care", "Welcome to Boldtrading soluton",
            "Hi FAITH CHEPNGENO,\n\nThanks for your registering on our Site! You can access various functionality from the menu on your left.\n\nHope you like our services, or feel free to comment, feedback or rebound!\n\nCheers~",
            datetime.now(), 'inbox', False),
    Message(2, "System Admin", "Password Reset Confirmation",
            "Your password has been reset successfully.",
            datetime(2025, 7, 15), 'inbox', True),
]

sample_notifications = [
    Notification("5394591", "Updated Personal Profile",
                 "You updated your person bio data. To check on the changes click on the header.",
                 "UnRead", "18th-Jul-2025 04:09:46 PM"),
    Notification("5396195", "Updated Personal Profile",
                 "You updated your person bio data. To check on the changes click on the header.",
                 "UnRead", "18th-Jul-2025 04:48:20 PM"),
]


@login_required
def user_messages(request):  # Renamed from messages to avoid conflict
    """Render the messages page"""
    folder = request.GET.get('folder', 'inbox')

    if folder == 'inbox':
        folder_messages = [m for m in sample_messages if m.folder == 'inbox']
    elif folder == 'sent':
        folder_messages = [m for m in sample_messages if m.folder == 'sent']
    elif folder == 'draft':
        folder_messages = [m for m in sample_messages if m.folder == 'draft']
    elif folder == 'trash':
        folder_messages = [m for m in sample_messages if m.folder == 'trash']
    else:
        folder_messages = sample_messages

    counts = {
        'inbox': len([m for m in sample_messages if m.folder == 'inbox' and not m.read]),
        'sent': len([m for m in sample_messages if m.folder == 'sent']),
        'draft': len([m for m in sample_messages if m.folder == 'draft']),
        'starred': 0,
        'trash': len([m for m in sample_messages if m.folder == 'trash']),
    }

    context = {
        'user': request.user,
        'folder': folder,
        'messages': folder_messages,
        'counts': counts,
        'current_message_id': request.GET.get('message_id'),
    }
    return render(request, 'polls/messages.html', context)


@login_required
def notifications(request):
    """Render the notifications page"""
    page_number = request.GET.get('page', 1)
    entries_per_page = int(request.GET.get('entries', 10))

    paginator = Paginator(sample_notifications, entries_per_page)
    page_obj = paginator.get_page(page_number)

    status_counts = {
        'total': len(sample_notifications),
        'unread': len([n for n in sample_notifications if n.status == 'UnRead']),
        'read': len([n for n in sample_notifications if n.status == 'Read']),
    }

    context = {
        'user': request.user,
        'notifications': page_obj,
        'status_counts': status_counts,
        'page_obj': page_obj,
        'entries_per_page': entries_per_page,
    }
    return render(request, 'polls/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def compose_message(request):
    """Handle composing a new message"""
    if request.method == 'POST':
        sender = request.user.username
        recipient = request.POST.get('recipient')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        new_message = Message(
            id=len(sample_messages) + 1,
            sender=sender,
            subject=subject,
            body=body,
            timestamp=datetime.now(),
            folder='sent'
        )
        sample_messages.append(new_message)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message_id': new_message.id})
        return redirect('messages')

    return redirect('messages')


@login_required
def view_message(request, message_id):
    """View a specific message and mark as read"""
    message = next((m for m in sample_messages if m.id == message_id), None)
    if not message:
        return JsonResponse({'error': 'Message not found'}, status=404)

    message.read = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'id': message.id,
            'sender': message.sender,
            'subject': message.subject,
            'body': message.body,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'read': message.read
        })

    return redirect('messages')


@login_required
@require_http_methods(["POST"])
def reply_message(request, message_id):
    """Handle replying to a message"""
    original_message = next((m for m in sample_messages if m.id == message_id), None)
    if not original_message:
        return JsonResponse({'error': 'Message not found'}, status=404)

    if request.method == 'POST':
        sender = request.user.username
        subject = f"Re: {original_message.subject}"
        body = request.POST.get('body', '')

        reply = Message(
            id=len(sample_messages) + 1,
            sender=sender,
            subject=subject,
            body=body,
            timestamp=datetime.now(),
            folder='sent'
        )
        sample_messages.append(reply)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message_id': reply.id})

    return redirect('messages')


@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Move message to trash or delete permanently"""
    message = next((m for m in sample_messages if m.id == message_id), None)
    if not message:
        return JsonResponse({'error': 'Message not found'}, status=404)

    if request.POST.get('permanent', 'false') == 'true':
        sample_messages.remove(message)
    else:
        message.folder = 'trash'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('messages')


@login_required
@require_http_methods(["POST"])
def mark_message_read(request, message_id):
    """Mark a message as read"""
    message = next((m for m in sample_messages if m.id == message_id), None)
    if not message:
        return JsonResponse({'error': 'Message not found'}, status=404)

    message.read = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('messages')


@login_required
def api_messages(request):
    """API endpoint for messages (AJAX)"""
    folder = request.GET.get('folder', 'inbox')

    if folder == 'inbox':
        filtered = [m for m in sample_messages if m.folder == 'inbox']
    elif folder == 'sent':
        filtered = [m for m in sample_messages if m.folder == 'sent']
    elif folder == 'draft':
        filtered = [m for m in sample_messages if m.folder == 'draft']
    elif folder == 'trash':
        filtered = [m for m in sample_messages if m.folder == 'trash']
    else:
        filtered = sample_messages

    messages_list = [
        {
            'id': m.id,
            'sender': m.sender,
            'subject': m.subject,
            'body': m.body,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'folder': m.folder,
            'read': m.read
        }
        for m in filtered
    ]

    return JsonResponse({'messages': messages_list})


@login_required
def api_notifications(request):
    """API endpoint for notifications (AJAX)"""
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')

    filtered = sample_notifications

    if status_filter != 'all':
        filtered = [n for n in filtered if n.status == status_filter]

    if search_query:
        filtered = [n for n in filtered
                    if search_query.lower() in n.title.lower()
                    or search_query.lower() in n.description.lower()]

    notifications_list = [
        {
            'id': n.id,
            'title': n.title,
            'description': n.description,
            'status': n.status,
            'date': n.date
        }
        for n in filtered
    ]

    return JsonResponse({'notifications': notifications_list})


@login_required
def api_notification_counts(request):
    """API endpoint for notification counts"""
    counts = {
        'total': len(sample_notifications),
        'unread': len([n for n in sample_notifications if n.status == 'UnRead']),
        'read': len([n for n in sample_notifications if n.status == 'Read']),
    }
    return JsonResponse(counts)


@login_required
@require_http_methods(["POST"])
def edit_notification(request, notification_id):
    """Edit a notification"""
    notification = next((n for n in sample_notifications if n.id == notification_id), None)
    if not notification:
        return JsonResponse({'error': 'Notification not found'}, status=404)

    if request.method == 'POST':
        data = json.loads(request.body) if request.body else request.POST
        notification.title = data.get('title', notification.title)
        notification.description = data.get('description', notification.description)
        notification.status = data.get('status', notification.status)

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@require_http_methods(["POST"])
def delete_notification(request, notification_id):
    """Delete a notification"""
    notification = next((n for n in sample_notifications if n.id == notification_id), None)
    if not notification:
        return JsonResponse({'error': 'Notification not found'}, status=404)

    sample_notifications.remove(notification)

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def toggle_notification_status(request, notification_id):
    """Toggle notification status between Read and UnRead"""
    notification = next((n for n in sample_notifications if n.id == notification_id), None)
    if not notification:
        return JsonResponse({'error': 'Notification not found'}, status=404)

    notification.status = 'Read' if notification.status == 'UnRead' else 'UnRead'

    return JsonResponse({'success': True, 'new_status': notification.status})


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    for notification in sample_notifications:
        notification.status = 'Read'

    return JsonResponse({'success': True})


# ==================== TRADING PLATFORM ====================
@login_required
def trading_platform(request):
    """Render the trading platform page"""
    user = request.user
    user_first_name = user.first_name or user.username

    trading_data = {
        'balance': 12500.75,
        'profit_today': 345.25,
        'total_trades': 42,
        'success_rate': 78.5,
        'portfolio_value': 15678.90,
    }

    recent_trades = [
        {'symbol': 'BTC/USD', 'type': 'Buy', 'amount': 0.5, 'price': 45231.50, 'time': '10:30 AM', 'profit': 245.75},
        {'symbol': 'ETH/USD', 'type': 'Sell', 'amount': 2.1, 'price': 3125.80, 'time': '09:15 AM', 'profit': 156.30},
        {'symbol': 'AAPL', 'type': 'Buy', 'amount': 10, 'price': 178.45, 'time': 'Yesterday', 'profit': 45.20},
        {'symbol': 'GOOGL', 'type': 'Sell', 'amount': 5, 'price': 145.90, 'time': 'Yesterday', 'profit': -23.50},
    ]

    market_data = [
        {'symbol': 'BTC/USD', 'price': 45231.50, 'change': 2.45, 'volume': '2.5B'},
        {'symbol': 'ETH/USD', 'price': 3125.80, 'change': 1.25, 'volume': '1.8B'},
        {'symbol': 'AAPL', 'price': 178.45, 'change': 0.85, 'volume': '125M'},
        {'symbol': 'GOOGL', 'price': 145.90, 'change': -0.35, 'volume': '85M'},
        {'symbol': 'TSLA', 'price': 245.60, 'change': 3.15, 'volume': '95M'},
        {'symbol': 'MSFT', 'price': 415.25, 'change': 1.45, 'volume': '110M'},
    ]

    context = {
        'user': user,
        'user_first_name': user_first_name,
        'trading_data': trading_data,
        'recent_trades': recent_trades,
        'market_data': market_data,
        'current_time': datetime.now().strftime("%I:%M %p"),
        'current_date': datetime.now().strftime("%B %d, %Y"),
    }

    return render(request, 'trading_platform.html', context)


@login_required
def get_live_data(request):
    """API endpoint for live trading data"""
    symbols = ['BTC/USD', 'ETH/USD', 'AAPL', 'GOOGL', 'TSLA', 'MSFT']

    live_data = []
    for symbol in symbols:
        base_price = {
            'BTC/USD': 45231.50,
            'ETH/USD': 3125.80,
            'AAPL': 178.45,
            'GOOGL': 145.90,
            'TSLA': 245.60,
            'MSFT': 415.25,
        }[symbol]

        change = random.uniform(-0.5, 0.5)
        new_price = base_price * (1 + change / 100)

        live_data.append({
            'symbol': symbol,
            'price': round(new_price, 2),
            'change': round(change, 2),
            'time': datetime.now().strftime("%H:%M:%S")
        })

    return JsonResponse({'live_data': live_data})


# My_app/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import Transaction, Wallet
from .forms import DepositForm
import json
import csv
from django.http import HttpResponse
from datetime import datetime, timedelta
from .tasks import process_pending_transactions, send_transaction_email


@login_required
def transaction_status_api(request, transaction_id):
    """API to get transaction status"""
    try:
        txn = Transaction.objects.get(transaction_id=transaction_id, user=request.user)

        return JsonResponse({
            'success': True,
            'transaction': {
                'id': txn.id,
                'transaction_id': str(txn.transaction_id),
                'reference': txn.reference,
                'txn_type': txn.txn_type,
                'amount': str(txn.amount),
                'currency': txn.currency,
                'status': txn.status,
                'payment_method': txn.payment_method,
                'payment_gateway': txn.payment_gateway,
                'gateway_transaction_id': txn.gateway_transaction_id,
                'fee_amount': str(txn.fee_amount) if txn.fee_amount else '0.00',
                'net_amount': str(txn.net_amount) if txn.net_amount else str(txn.amount),
                'created_at': txn.created_at.isoformat(),
                'updated_at': txn.updated_at.isoformat(),
                'completed_at': txn.completed_at.isoformat() if txn.completed_at else None,
                'expires_at': txn.expires_at.isoformat() if txn.expires_at else None,
                'metadata': txn.metadata,
                'gateway_response': txn.gateway_response,
                'can_refund': txn.can_refund(),
                'balance_before': str(txn.balance_before) if txn.balance_before else None,
                'balance_after': str(txn.balance_after) if txn.balance_after else None,
            }
        })
    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found'
        }, status=404)


@login_required
def transaction_retry_api(request, transaction_id):
    """API to retry a failed transaction"""
    if request.method == 'POST':
        try:
            txn = Transaction.objects.get(transaction_id=transaction_id, user=request.user)

            if txn.status not in ['FAILED', 'EXPIRED']:
                return JsonResponse({
                    'success': False,
                    'error': 'Only failed or expired transactions can be retried'
                })

            # Create a new transaction based on the failed one
            new_txn = Transaction.objects.create(
                user=request.user,
                txn_type=txn.txn_type,
                amount=txn.amount,
                currency=txn.currency,
                payment_method=txn.payment_method,
                payment_gateway=txn.payment_gateway,
                metadata=txn.metadata,
                description=f"Retry of transaction {txn.reference}",
                status='PENDING'
            )

            # Process the transaction
            from .tasks import process_pending_transactions
            process_pending_transactions.delay()

            return JsonResponse({
                'success': True,
                'message': 'Transaction retry initiated',
                'new_transaction_id': str(new_txn.transaction_id),
                'new_reference': new_txn.reference
            })

        except Transaction.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Transaction not found'
            }, status=404)

    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)


@login_required
def transaction_refund_api(request, transaction_id):
    """API to request a refund"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = data.get('amount')
            reason = data.get('reason', '')

            txn = Transaction.objects.get(transaction_id=transaction_id, user=request.user)

            if not txn.can_refund():
                return JsonResponse({
                    'success': False,
                    'error': 'Transaction cannot be refunded'
                })

            # Create refund transaction
            refund_amount = float(amount) if amount else float(txn.amount)

            if refund_amount > float(txn.amount):
                return JsonResponse({
                    'success': False,
                    'error': 'Refund amount cannot exceed original amount'
                })

            refund_txn = txn.create_refund(
                amount=refund_amount,
                admin_notes=reason
            )

            # Process refund
            from .tasks import process_pending_transactions
            process_pending_transactions.delay()

            return JsonResponse({
                'success': True,
                'message': 'Refund request submitted',
                'refund_transaction_id': str(refund_txn.transaction_id),
                'refund_reference': refund_txn.reference,
                'amount': str(refund_amount)
            })

        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        except Transaction.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Transaction not found'
            }, status=404)

    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)


@login_required
def live_transactions_api(request):
    """API for live transaction updates (for AJAX polling)"""
    last_update = request.GET.get('last_update')

    # Get user's transactions
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]

    # Calculate stats
    stats = {
        'total': transactions.count(),
        'completed': transactions.filter(status='COMPLETED').count(),
        'pending': transactions.filter(status__in=['PENDING', 'PROCESSING']).count(),
        'failed': transactions.filter(status__in=['FAILED', 'EXPIRED', 'CANCELLED']).count(),
        'balance': str(request.user.wallet.balance) if hasattr(request.user, 'wallet') else '0.00'
    }

    # Filter transactions if last_update provided
    if last_update:
        try:
            last_update_dt = timezone.datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            transactions = transactions.filter(updated_at__gt=last_update_dt)
        except:
            pass

    transactions_list = []
    for txn in transactions:
        transactions_list.append({
            'id': txn.id,
            'transaction_id': str(txn.transaction_id),
            'reference': txn.reference,
            'txn_type': txn.txn_type,
            'amount': str(txn.amount),
            'currency': txn.currency,
            'status': txn.status,
            'payment_method': txn.payment_method,
            'payment_gateway': txn.payment_gateway,
            'fee_amount': str(txn.fee_amount) if txn.fee_amount else '0.00',
            'net_amount': str(txn.net_amount) if txn.net_amount else str(txn.amount),
            'created_at': txn.created_at.isoformat(),
            'updated_at': txn.updated_at.isoformat(),
            'completed_at': txn.completed_at.isoformat() if txn.completed_at else None,
            'expires_at': txn.expires_at.isoformat() if txn.expires_at else None,
            'metadata': txn.metadata,
            'can_refund': txn.can_refund(),
            'payment_method_icon': txn.payment_method_icon,
            'formatted_amount': txn.formatted_amount
        })

    return JsonResponse({
        'success': True,
        'transactions': transactions_list,
        'stats': stats,
        'last_update': timezone.now().isoformat()
    })


@login_required
def export_transactions_api(request):
    """API to export transactions as CSV"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{timezone.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Transaction ID', 'Reference', 'Type', 'Amount', 'Currency', 'Status',
        'Payment Method', 'Fee', 'Net Amount', 'Created At', 'Completed At'
    ])

    for txn in transactions:
        writer.writerow([
            txn.transaction_id,
            txn.reference,
            txn.txn_type,
            str(txn.amount),
            txn.currency,
            txn.status,
            txn.payment_method or '',
            str(txn.fee_amount) if txn.fee_amount else '0.00',
            str(txn.net_amount) if txn.net_amount else str(txn.amount),
            txn.created_at.isoformat(),
            txn.completed_at.isoformat() if txn.completed_at else ''
        ])

    return response


@csrf_exempt
def webhook_mpesa(request):
    """Webhook endpoint for M-Pesa callbacks"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Verify webhook signature (in production)
            # signature = request.headers.get('X-Mpesa-Signature')

            # Find transaction by reference
            callback_metadata = data.get('Body', {}).get('stkCallback', {})
            checkout_request_id = callback_metadata.get('CheckoutRequestID')

            if checkout_request_id:
                # Find transaction by metadata
                transactions = Transaction.objects.filter(
                    metadata__contains={'checkout_request_id': checkout_request_id}
                )

                if transactions.exists():
                    txn = transactions.first()

                    result_code = callback_metadata.get('ResultCode')
                    result_desc = callback_metadata.get('ResultDesc')

                    if result_code == 0:
                        # Success
                        txn.status = 'COMPLETED'
                        txn.gateway_response = data
                        txn.gateway_status = 'CAPTURED'

                        # Extract M-Pesa transaction details
                        callback_items = callback_metadata.get('CallbackMetadata', {}).get('Item', [])
                        for item in callback_items:
                            if item.get('Name') == 'MpesaReceiptNumber':
                                txn.gateway_transaction_id = item.get('Value')
                            elif item.get('Name') == 'Amount':
                                # Verify amount matches
                                pass

                        # Update wallet
                        wallet, created = Wallet.objects.get_or_create(user=txn.user)
                        wallet.balance += txn.amount
                        wallet.save()

                        txn.balance_after = wallet.balance

                    else:
                        # Failed
                        txn.status = 'FAILED'
                        txn.gateway_response = data
                        txn.gateway_status = 'DECLINED'

                    txn.save()

                    # Send email notification
                    send_transaction_email.delay(txn.id)

                    return JsonResponse({'success': True})

            return JsonResponse({'success': False, 'error': 'Transaction not found'}, status=404)

        except Exception as e:
            print(f"Webhook error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def webhook_stripe(request):
    """Webhook endpoint for Stripe callbacks"""
    if request.method == 'POST':
        try:
            import stripe
            # stripe.api_key = settings.STRIPE_SECRET_KEY

            payload = request.body
            sig_header = request.headers.get('Stripe-Signature')

            # Verify webhook signature
            # event = stripe.Webhook.construct_event(
            #     payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            # )

            data = json.loads(payload)
            event_type = data.get('type')

            if event_type == 'payment_intent.succeeded':
                payment_intent = data.get('data', {}).get('object', {})
                transaction_id = payment_intent.get('metadata', {}).get('transaction_id')

                if transaction_id:
                    try:
                        txn = Transaction.objects.get(transaction_id=transaction_id)
                        txn.status = 'COMPLETED'
                        txn.gateway_transaction_id = payment_intent.get('id')
                        txn.gateway_response = data
                        txn.gateway_status = 'CAPTURED'
                        txn.completed_at = timezone.now()

                        # Update wallet
                        wallet, created = Wallet.objects.get_or_create(user=txn.user)
                        wallet.balance += txn.amount
                        wallet.save()

                        txn.balance_after = wallet.balance
                        txn.save()

                        # Send email
                        send_transaction_email.delay(txn.id)

                    except Transaction.DoesNotExist:
                        pass

            elif event_type == 'payment_intent.payment_failed':
                payment_intent = data.get('data', {}).get('object', {})
                transaction_id = payment_intent.get('metadata', {}).get('transaction_id')

                if transaction_id:
                    try:
                        txn = Transaction.objects.get(transaction_id=transaction_id)
                        txn.status = 'FAILED'
                        txn.gateway_response = data
                        txn.gateway_status = 'DECLINED'
                        txn.save()

                        # Send email
                        send_transaction_email.delay(txn.id)

                    except Transaction.DoesNotExist:
                        pass

            return JsonResponse({'success': True})

        except Exception as e:
            print(f"Stripe webhook error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required
def transaction_stats_api(request):
    """API to get transaction statistics"""
    # Daily stats for last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)

    daily_stats = Transaction.objects.filter(
        user=request.user,
        created_at__gte=thirty_days_ago
    ).extra({
        'date': "date(created_at)"
    }).values('date').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        completed=Count('id', filter=Q(status='COMPLETED')),
        failed=Count('id', filter=Q(status='FAILED'))
    ).order_by('date')

    # Monthly stats
    monthly_stats = Transaction.objects.filter(
        user=request.user
    ).extra({
        'month': "strftime('%Y-%m', created_at)"
    }).values('month').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('month')

    # Payment method breakdown
    payment_method_stats = Transaction.objects.filter(
        user=request.user
    ).values('payment_method').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        success_rate=Count('id', filter=Q(status='COMPLETED')) * 100.0 / Count('id')
    )

    return JsonResponse({
        'success': True,
        'daily_stats': list(daily_stats),
        'monthly_stats': list(monthly_stats),
        'payment_method_stats': list(payment_method_stats),
        'wallet_balance': str(request.user.wallet.balance) if hasattr(request.user, 'wallet') else '0.00'
    })


@csrf_exempt
def webhook_paypal(request):
    """Webhook endpoint for PayPal callbacks"""
    if request.method == 'POST':
        try:
            import paypalrestsdk
            # In production, verify the webhook signature
            # event_body = request.body.decode('utf-8')
            # webhook_id = settings.PAYPAL_WEBHOOK_ID

            data = json.loads(request.body)
            event_type = data.get('event_type')
            resource = data.get('resource', {})

            if event_type == 'PAYMENT.CAPTURE.COMPLETED':
                # Payment completed
                capture_id = resource.get('id')
                transaction_id = resource.get('custom_id') or resource.get('invoice_id')

                if transaction_id:
                    try:
                        txn = Transaction.objects.get(transaction_id=transaction_id)
                        txn.status = 'COMPLETED'
                        txn.gateway_transaction_id = capture_id
                        txn.gateway_response = data
                        txn.gateway_status = 'CAPTURED'
                        txn.completed_at = timezone.now()

                        # Update wallet
                        wallet, created = Wallet.objects.get_or_create(user=txn.user)
                        wallet.balance += txn.amount
                        wallet.save()

                        txn.balance_after = wallet.balance
                        txn.save()

                        # Send email
                        send_transaction_email.delay(txn.id)

                    except Transaction.DoesNotExist:
                        print(f"PayPal webhook: Transaction not found: {transaction_id}")

            elif event_type == 'PAYMENT.CAPTURE.DENIED':
                # Payment failed
                capture_id = resource.get('id')
                transaction_id = resource.get('custom_id') or resource.get('invoice_id')

                if transaction_id:
                    try:
                        txn = Transaction.objects.get(transaction_id=transaction_id)
                        txn.status = 'FAILED'
                        txn.gateway_response = data
                        txn.gateway_status = 'DECLINED'
                        txn.save()

                        # Send email
                        send_transaction_email.delay(txn.id)

                    except Transaction.DoesNotExist:
                        print(f"PayPal webhook: Transaction not found: {transaction_id}")

            elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
                # Payment refunded
                refund_id = resource.get('id')
                capture_id = resource.get('capture_id')

                # Find transaction by capture_id
                if capture_id:
                    try:
                        txn = Transaction.objects.get(gateway_transaction_id=capture_id)

                        # Create refund transaction
                        refund_amount = float(resource.get('amount', {}).get('value', 0))
                        txn.create_refund(
                            amount=refund_amount,
                            admin_notes='Refund via PayPal webhook'
                        )

                    except Transaction.DoesNotExist:
                        print(f"PayPal webhook: Transaction not found for capture_id: {capture_id}")

            return JsonResponse({'success': True})

        except Exception as e:
            print(f"PayPal webhook error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


# My_app/views.py - Add this function if you need Stripe
@csrf_exempt
def webhook_stripe(request):
    """Webhook endpoint for Stripe callbacks"""
    if request.method == 'POST':
        try:
            # For now, just return success without actual Stripe integration
            data = json.loads(request.body)
            print(f"Stripe webhook received: {data.get('type', 'Unknown event')}")

            # TODO: Implement actual Stripe webhook verification and processing
            # stripe.api_key = settings.STRIPE_SECRET_KEY
            # sig_header = request.headers.get('Stripe-Signature')
            # event = stripe.Webhook.construct_event(
            #     request.body, sig_header, settings.STRIPE_WEBHOOK_SECRET
            # )

            return JsonResponse({'success': True, 'message': 'Webhook received'})

        except Exception as e:
            print(f"Stripe webhook error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


from decimal import Decimal
import random
import time
from datetime import datetime
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json


# ==================== PAYMENT PROCESSING ====================
@login_required
def deposit_funds(request):
    """Process deposit request - Enhanced version"""
    if request.method == 'POST':
        try:
            # Handle AJAX requests differently
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return handle_ajax_deposit(request)

            # Get form data
            data = request.POST
            currency = data.get('currency')
            payment_method = data.get('payment_method')
            terms_accepted = data.get('terms_accepted')
            final_amount = data.get('final_amount')
            payment_details = data.get('payment_details', '{}')

            # Parse payment details if provided
            try:
                details = json.loads(payment_details) if payment_details else {}
            except:
                details = {}

            # Validation
            if not currency:
                messages.error(request, "Please select a currency")
                return render(request, 'polls/deposit.html')

            if not payment_method:
                messages.error(request, "Please select a payment method")
                return render(request, 'polls/deposit.html')

            if not terms_accepted:
                messages.error(request, "You must accept the terms and conditions")
                return render(request, 'polls/deposit.html')

            if not final_amount:
                messages.error(request, "Please select an amount")
                return render(request, 'polls/deposit.html')

            try:
                amount = Decimal(final_amount)
            except:
                messages.error(request, "Invalid amount")
                return render(request, 'polls/deposit.html')

            if amount < Decimal('1') or amount > Decimal('10000'):
                messages.error(request, "Amount must be between 1 and 10,000")
                return render(request, 'polls/deposit.html')

            # Process payment details
            metadata = details  # Use details from the form

            # Override with form data if available
            if payment_method == 'mpesa':
                mpesa_phone = data.get('mpesa_phone', '')
                if mpesa_phone:
                    metadata.update({
                        'phone_number': mpesa_phone,
                        'provider': 'M-Pesa',
                        'country': 'Kenya'
                    })

            elif payment_method == 'card':
                card_number = data.get('card_number', '')
                if card_number:
                    card_last_four = card_number[-4:] if len(card_number) >= 4 else '****'
                    metadata.update({
                        'card_last_four': card_last_four,
                        'card_type': 'visa' if card_number.startswith('4') else 'mastercard',
                        'card_name': data.get('card_name', ''),
                        'provider': 'Card Payment'
                    })

            elif payment_method == 'paypal':
                metadata.update({'provider': 'PayPal'})

            elif payment_method == 'alipay':
                metadata.update({'provider': 'Alipay'})

            # Create transaction with PENDING status initially
            transaction_id = f"DEP{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            transaction = Transaction.objects.create(
                user=request.user,
                transaction_id=transaction_id,
                transaction_type='DEPOSIT',
                amount=amount,
                currency=currency,
                status='PENDING',  # Start as pending
                payment_method=payment_method,
                payment_reference=f"REF{int(time.time())}",
                metadata=metadata
            )

            # Start async processing
            from .tasks import process_pending_transactions
            process_pending_transactions.delay(transaction.id)

            messages.success(request, f"Deposit of {currency}{amount:.2f} is being processed!")

            # Return JSON for AJAX or redirect for regular form
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': '/transactions/',
                    'message': f"Deposit of {currency}{amount:.2f} is being processed!"
                })
            else:
                return redirect('transactions')

        except Exception as e:
            error_msg = f"Error processing deposit: {str(e)}"
            messages.error(request, error_msg)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                return render(request, 'deposit.html')

    # GET request - show deposit form
    return render(request, 'polls/deposit.html')


def handle_ajax_deposit(request):
    """Handle AJAX deposit requests specifically"""
    try:
        data = json.loads(request.body)

        # Extract data
        currency = data.get('currency')
        payment_method = data.get('payment_method')
        final_amount = data.get('final_amount')
        payment_details = data.get('payment_details', '{}')

        # Validation
        if not all([currency, payment_method, final_amount]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        try:
            amount = Decimal(final_amount)
        except:
            return JsonResponse({
                'success': False,
                'error': 'Invalid amount'
            }, status=400)

        if amount < Decimal('1') or amount > Decimal('10000'):
            return JsonResponse({
                'success': False,
                'error': 'Amount must be between 1 and 10,000'
            }, status=400)

        # Create transaction
        transaction_id = f"DEP{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

        transaction = Transaction.objects.create(
            user=request.user,
            transaction_id=transaction_id,
            transaction_type='DEPOSIT',
            amount=amount,
            currency=currency,
            status='PENDING',
            payment_method=payment_method,
            payment_reference=f"REF{int(time.time())}",
            metadata=json.loads(payment_details)
        )

        # Start async processing
        from .tasks import process_pending_transactions
        process_pending_transactions.delay(transaction.id)

        return JsonResponse({
            'success': True,
            'transaction': {
                'id': transaction.id,
                'transaction_id': str(transaction.transaction_id),
                'reference': transaction.payment_reference,
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'status': transaction.status,
                'payment_method': transaction.payment_method,
                'created_at': transaction.created_at.isoformat()
            },
            'redirect_url': '/transactions/',
            'message': f"Deposit of {currency}{amount:.2f} is being processed!"
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def check_transaction_status(request, transaction_id):
    """Check status of a transaction"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user
        )

        return JsonResponse({
            'success': True,
            'transaction': {
                'id': transaction.id,
                'transaction_id': str(transaction.transaction_id),
                'status': transaction.status,
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'created_at': transaction.created_at.isoformat()
            }
        })
    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found'
        }, status=404)


# views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
import json
from decimal import Decimal
from datetime import datetime
import random
import time


@login_required
def withdraw_funds(request):
    """Process withdrawal request - AJAX compatible"""
    if request.method == 'POST':
        try:
            # Get form data
            data = request.POST
            amount = data.get('amount')
            currency = data.get('currency', 'USD')
            withdraw_method = data.get('withdraw_method')
            withdraw_details = data.get('withdraw_details', '{}')
            terms_accepted = data.get('terms_accepted')

            # Parse withdrawal details
            try:
                details = json.loads(withdraw_details) if withdraw_details else {}
            except:
                details = {}

            # Validation
            errors = {}

            # Validate amount
            try:
                withdraw_amount = Decimal(amount) if amount else Decimal('0')
                if withdraw_amount < Decimal('10'):
                    errors['amount'] = ['Minimum withdrawal amount is $10']
                if withdraw_amount > Decimal('5000'):
                    errors['amount'] = ['Maximum withdrawal amount is $5,000']
            except:
                errors['amount'] = ['Invalid amount']

            # Check user balance
            user_wallet = Wallet.objects.get(user=request.user)
            if withdraw_amount > user_wallet.balance:
                errors['amount'] = ['Insufficient balance']

            # Validate withdrawal method
            if not withdraw_method:
                errors['withdraw_method'] = ['Please select a withdrawal method']

            # Validate terms
            if not terms_accepted or terms_accepted.lower() != 'true':
                errors['terms'] = ['You must accept the terms and conditions']

            # Method-specific validation
            if withdraw_method == 'bank':
                account_name = data.get('account_name', '')
                account_number = data.get('account_number', '')
                if not account_name or len(account_name.strip()) < 2:
                    errors['accountName'] = ['Please enter valid account holder name']
                if not account_number or len(account_number) < 5:
                    errors['accountNumber'] = ['Please enter valid account number']

            elif withdraw_method == 'paypal':
                email = data.get('paypal_email', '')
                if not email or '@' not in email:
                    errors['paypalEmail'] = ['Please enter valid PayPal email']

            elif withdraw_method == 'mpesa':
                phone = data.get('mpesa_phone', '')
                if not phone or not phone.startswith('254'):
                    errors['mpesaPhone'] = ['Please enter valid M-Pesa phone number']

            elif withdraw_method == 'skrill':
                email = data.get('skrill_email', '')
                if not email or '@' not in email:
                    errors['skrillEmail'] = ['Please enter valid Skrill email']

            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)

            # Calculate fee based on method
            fee = Decimal('0')
            if withdraw_method == 'bank':
                fee = Decimal('5.00')
            elif withdraw_method == 'paypal':
                fee = (withdraw_amount * Decimal('0.02')).quantize(Decimal('0.01'))
            elif withdraw_method == 'mpesa':
                fee = (withdraw_amount * Decimal('0.01')).quantize(Decimal('0.01'))
            elif withdraw_method == 'skrill':
                fee = (withdraw_amount * Decimal('0.015')).quantize(Decimal('0.01'))

            # Minimum fee
            if fee < Decimal('0.50'):
                fee = Decimal('0.50')

            # Amount to receive
            receive_amount = withdraw_amount - fee

            # Create withdrawal transaction
            transaction_id = f"WTH{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            transaction = Transaction.objects.create(
                user=request.user,
                transaction_id=transaction_id,
                transaction_type='WITHDRAWAL',
                amount=withdraw_amount,
                currency=currency,
                status='PENDING',
                payment_method=withdraw_method,
                payment_reference=f"WREF{int(time.time())}",
                metadata={
                    **details,
                    'fee': str(fee),
                    'receive_amount': str(receive_amount),
                    'net_amount': str(withdraw_amount - fee)
                }
            )

            # Update wallet (deduct amount immediately)
            user_wallet.balance -= withdraw_amount
            user_wallet.save()

            # Start async processing for withdrawal
            from .tasks import process_withdrawal
            process_withdrawal.delay(transaction.id)

            message = f"Withdrawal of {currency}{withdraw_amount:.2f} submitted successfully!"

            return JsonResponse({
                'success': True,
                'message': message,
                'transaction_id': transaction_id,
                'withdrawal_amount': str(withdraw_amount),
                'fee': str(fee),
                'net_amount': str(receive_amount),
                'redirect_url': '/transactions/'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    # GET request - show withdrawal form
    user_wallet = Wallet.objects.get(user=request.user)
    return render(request, 'polls/withdraw.html', {
        'user_wallet': user_wallet
    })


from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_modify_balance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            action = data.get('action')
            amount = data.get('amount')
            description = data.get('description')

            # Get user and wallet
            user = User.objects.get(id=user_id)
            wallet = user.wallet

            # Calculate new balance
            old_balance = wallet.balance

            if action == 'ADD':
                new_balance = old_balance + amount
            elif action == 'SUBTRACT':
                new_balance = old_balance - amount
            elif action == 'SET':
                new_balance = amount
            elif action == 'BONUS':
                new_balance = old_balance + amount
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)

            # Update wallet
            wallet.balance = new_balance
            wallet.save()

            # Create audit log
            BalanceChange.objects.create(
                user=user,
                admin=request.user,
                old_balance=old_balance,
                new_balance=new_balance,
                change=new_balance - old_balance,
                description=description,
                transaction_type='ADMIN_MOD' if action != 'BONUS' else 'BONUS'
            )

            # Create transaction record
            transaction = Transaction.objects.create(
                user=user,
                transaction_type='ADMIN_MOD' if action != 'BONUS' else 'BONUS',
                amount=abs(new_balance - old_balance),
                status='COMPLETED',
                payment_method='ADMIN',
                description=description,
                metadata={
                    'admin': request.user.username,
                    'action': action,
                    'old_balance': str(old_balance),
                    'new_balance': str(new_balance)
                }
            )

            # Send WebSocket notification to user
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'transactions_{user.id}',
                {
                    'type': 'send_update',
                    'data': {
                        'type': 'ADMIN_MODIFICATION',
                        'admin': request.user.username,
                        'user': user.username,
                        'user_id': user.id,
                        'change': new_balance - old_balance,
                        'new_balance': new_balance,
                        'reason': description,
                        'timestamp': transaction.created_at.isoformat()
                    }
                }
            )

            # Send to admin notifications
            async_to_sync(channel_layer.group_send)(
                'admin_notifications',
                {
                    'type': 'send_update',
                    'data': {
                        'type': 'AUDIT_LOG',
                        'title': 'Balance Modified',
                        'message': f'{request.user.username} modified {user.username}\'s balance by ${new_balance - old_balance}',
                        'type': 'info'
                    }
                }
            )

            return JsonResponse({
                'success': True,
                'message': 'Balance updated successfully',
                'new_balance': new_balance
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)


# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from .models import ChatMessage, BroadcastMessage


@csrf_exempt
@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipient_id = data.get('recipient_id')
            message = data.get('message')

            # Save message
            ChatMessage.objects.create(
                sender=request.user,
                recipient_id=recipient_id,
                message=message
            )

            return JsonResponse({'status': 'success', 'message': 'Message sent'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@csrf_exempt
@login_required
def send_broadcast(request):
    if request.method == 'POST':
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'})

        try:
            data = json.loads(request.body)
            title = data.get('title')
            message = data.get('message')
            priority = data.get('priority', 'normal')
            broadcast_type = data.get('broadcast_type', 'announcement')

            # Save broadcast
            broadcast = BroadcastMessage.objects.create(
                sender=request.user,
                title=title,
                message=message,
                priority=priority,
                broadcast_type=broadcast_type
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Broadcast sent',
                'broadcast_id': broadcast.id
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def get_recent_messages(request):
    # Get recent messages for the user
    messages = ChatMessage.objects.filter(
        recipient=request.user
    ).order_by('-timestamp')[:20]

    data = [{
        'id': msg.id,
        'sender': msg.sender.username,
        'sender_id': msg.sender.id,
        'message': msg.message,
        'timestamp': msg.timestamp.isoformat(),
        'read': msg.read
    } for msg in messages]

    return JsonResponse({'messages': data})


# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import random
from .models import Transaction, Wallet
from .forms import DepositForm


# ==================== CORE DEPOSIT VIEW ====================

@login_required
def deposit(request):
    """Render deposit page"""
    return render(request, "polls/deposit.html", {})


@login_required
def process_deposit(request):
    """Process deposit request"""
    if request.method == 'POST':
        try:
            # Get form data directly from request.POST
            data = request.POST

            # Extract and validate required fields
            currency = data.get('currency')
            payment_method = data.get('payment_method')
            terms_accepted = data.get('terms_accepted')
            final_amount = data.get('final_amount')

            # Basic validation
            if not currency:
                messages.error(request, "Please select a currency")
                return redirect('deposit')

            if not payment_method:
                messages.error(request, "Please select a payment method")
                return redirect('deposit')

            if not terms_accepted:
                messages.error(request, "You must accept the terms and conditions")
                return redirect('deposit')

            if not final_amount:
                messages.error(request, "Please select an amount")
                return redirect('deposit')

            try:
                amount = Decimal(final_amount)
            except:
                messages.error(request, "Invalid amount")
                return redirect('deposit')

            # Validate amount range
            if amount < Decimal('1') or amount > Decimal('10000'):
                messages.error(request, "Amount must be between 1 and 10,000")
                return redirect('deposit')

            # Validate payment method specific data
            metadata = {}

            if payment_method == 'mpesa':
                mpesa_phone = data.get('mpesa_phone', '')
                if not mpesa_phone:
                    messages.error(request, "Please enter your M-Pesa phone number")
                    return redirect('deposit')

                if not mpesa_phone.startswith('254'):
                    messages.error(request, "M-Pesa phone number must start with 254")
                    return redirect('deposit')

                metadata = {
                    'phone_number': mpesa_phone,
                    'provider': 'M-Pesa',
                    'country': 'Kenya'
                }

            elif payment_method == 'card':
                card_number = data.get('card_number', '')
                card_expiry = data.get('card_expiry', '')
                card_cvv = data.get('card_cvv', '')
                card_name = data.get('card_name', '')

                if not card_number:
                    messages.error(request, "Please enter card number")
                    return redirect('deposit')
                if not card_expiry:
                    messages.error(request, "Please enter card expiry date")
                    return redirect('deposit')
                if not card_cvv:
                    messages.error(request, "Please enter card CVV")
                    return redirect('deposit')
                if not card_name:
                    messages.error(request, "Please enter name on card")
                    return redirect('deposit')

                # Store only last 4 digits for security
                card_last_four = card_number[-4:] if len(card_number) >= 4 else '****'
                metadata = {
                    'card_last_four': card_last_four,
                    'card_type': 'visa' if card_number.startswith('4') else 'mastercard',
                    'card_name': card_name,
                    'provider': 'Card Payment'
                }

            elif payment_method == 'paypal':
                metadata = {'provider': 'PayPal'}

            elif payment_method == 'alipay':
                metadata = {'provider': 'Alipay'}

            # Generate unique transaction ID
            transaction_id = f"DEP{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            # Create transaction record
            transaction = Transaction.objects.create(
                user=request.user,
                transaction_id=transaction_id,
                transaction_type='DEPOSIT',
                amount=amount,
                currency=currency,
                status='COMPLETED',  # For demo purposes - mark as completed
                payment_method=payment_method,
                payment_reference=f"REF{int(timezone.now().timestamp())}",
                metadata=metadata
            )

            # Update wallet balance
            try:
                wallet, created = Wallet.objects.get_or_create(
                    user=request.user,
                    defaults={'balance': Decimal('0'), 'currency': currency}
                )
                wallet.balance += amount
                wallet.save()
            except Exception as e:
                print(f"Wallet update error: {e}")
                # Continue even if wallet update fails

            # Success message
            messages.success(request, f"Deposit of {currency}{amount:.2f} completed successfully!")

            # Redirect to transactions page
            return redirect('transactions')

        except Exception as e:
            print(f"Error in process_deposit: {str(e)}")
            messages.error(request, f"Error processing deposit: {str(e)}")
            return redirect('deposit')

    # If not POST, redirect to deposit page
    return redirect('deposit')


# ==================== TRANSACTION VIEWS ====================

@login_required
def transactions(request):
    """View all transactions"""
    user_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

    # Calculate stats
    total_amount = Decimal('0')
    deposit_count = 0
    success_rate = 100

    if user_transactions.exists():
        completed_transactions = user_transactions.filter(status='COMPLETED')

        # Calculate total amount
        total_sum = completed_transactions.aggregate(total=Sum('amount'))['total']
        total_amount = total_sum if total_sum else Decimal('0')

        # Count deposits
        deposit_count = user_transactions.filter(
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).count()

        # Calculate success rate
        total_completed = completed_transactions.count()
        total_all = user_transactions.count()
        success_rate = round((total_completed / total_all * 100), 2) if total_all > 0 else 100

    context = {
        'transactions': user_transactions,
        'total_amount': f"{total_amount:.2f}",
        'deposit_count': deposit_count,
        'success_rate': success_rate,
    }

    return render(request, "polls/transactions.html", context)


@login_required
def transaction_status(request, transaction_id):
    """Show transaction status page"""
    try:
        transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
    except Transaction.DoesNotExist:
        messages.error(request, "Transaction not found")
        return redirect('transactions')

    context = {
        'transaction': transaction,
    }

    return render(request, "polls/transaction_status.html", context)


# ==================== API ENDPOINTS ====================

@login_required
def api_live_transactions(request):
    """API endpoint for live transaction updates"""
    last_update = request.GET.get('last_update')

    try:
        if last_update:
            try:
                # Parse the date string manually without dateutil
                # Try different date formats
                try:
                    # ISO format
                    last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                except:
                    try:
                        # Try parsing with strptime
                        from datetime import datetime
                        formats = [
                            '%Y-%m-%dT%H:%M:%S.%fZ',
                            '%Y-%m-%dT%H:%M:%SZ',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%d'
                        ]
                        for fmt in formats:
                            try:
                                last_update_dt = datetime.strptime(last_update, fmt)
                                break
                            except:
                                continue
                        else:
                            raise ValueError("Could not parse date")
                    except:
                        # If parsing fails, ignore the last_update parameter
                        last_update_dt = None

                if last_update_dt:
                    new_transactions = Transaction.objects.filter(
                        user=request.user,
                        updated_at__gt=last_update_dt
                    ).order_by('-created_at')[:20]
                else:
                    new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:20]
            except:
                new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:20]
        else:
            new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:20]

        # Serialize transactions
        transactions_data = []
        for txn in new_transactions:
            transactions_data.append({
                'id': txn.id,
                'transaction_id': str(txn.transaction_id),
                'amount': float(txn.amount),
                'currency': txn.currency,
                'payment_method': txn.payment_method,
                'payment_reference': txn.payment_reference or '',
                'status': txn.status.lower(),
                'metadata': txn.metadata if txn.metadata else {},
                'created_at': txn.created_at.isoformat(),
                'updated_at': txn.updated_at.isoformat(),
            })

        # Get stats
        total_deposits = Transaction.objects.filter(
            user=request.user,
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).count()

        total_amount_result = Transaction.objects.filter(
            user=request.user,
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))

        total_amount = str(total_amount_result['total'] or '0')

        return JsonResponse({
            'success': True,
            'transactions': transactions_data,
            'last_update': timezone.now().isoformat(),
            'stats': {
                'total_deposits': total_deposits,
                'total_amount': total_amount,
            }
        })

    except Exception as e:
        print(f"Error in api_live_transactions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'transactions': [],
            'last_update': timezone.now().isoformat()
        })


@login_required
def api_transaction_details(request, transaction_id):
    """API endpoint for transaction details"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user
        )
        return JsonResponse({
            'success': True,
            'transaction': {
                'transaction_id': str(transaction.transaction_id),
                'amount': float(transaction.amount),
                'currency': transaction.currency,
                'payment_method': transaction.payment_method,
                'payment_reference': transaction.payment_reference,
                'status': transaction.status.lower(),
                'metadata': transaction.metadata if transaction.metadata else {},
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'user_email': request.user.email,
            }
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transaction not found'})


@login_required
@require_POST
def api_retry_transaction(request, transaction_id):
    """API endpoint to retry a failed transaction"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user,
            status='FAILED'  # Only allow retry for failed transactions
        )

        # Create a new transaction as retry
        new_transaction_id = f"RETRY{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

        new_transaction = Transaction.objects.create(
            user=request.user,
            transaction_id=new_transaction_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.currency,
            status='PENDING',
            payment_method=transaction.payment_method,
            payment_reference=f"RETRY{int(timezone.now().timestamp())}",
            metadata=transaction.metadata if transaction.metadata else {}
        )

        return JsonResponse({
            'success': True,
            'message': 'Retry initiated',
            'new_transaction_id': new_transaction.transaction_id
        })

    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found or cannot be retried'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ==================== PAYMENT CALLBACKS ====================

@csrf_exempt
@require_POST
def mpesa_callback(request):
    """M-Pesa payment callback"""
    try:
        # Parse the callback data
        data = json.loads(request.body)
        print("M-Pesa Callback:", data)  # Debugging

        # Check if it's a valid callback
        if 'Body' in data and 'stkCallback' in data['Body']:
            callback = data['Body']['stkCallback']
            checkout_request_id = callback.get('CheckoutRequestID')
            result_code = callback.get('ResultCode')

            if result_code == 0:
                # Payment successful
                try:
                    transaction = Transaction.objects.get(
                        gateway_transaction_id=checkout_request_id,
                        status='PENDING'
                    )
                    transaction.status = 'COMPLETED'
                    if transaction.metadata:
                        transaction.metadata['mpesa_callback'] = callback
                    else:
                        transaction.metadata = {'mpesa_callback': callback}
                    transaction.save()

                    # Update wallet
                    try:
                        wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                        wallet.balance += transaction.amount
                        wallet.save()
                    except:
                        pass

                except Transaction.DoesNotExist:
                    pass

                return JsonResponse({
                    "ResultCode": 0,
                    "ResultDesc": "Success"
                })

        return JsonResponse({
            "ResultCode": 0,
            "ResultDesc": "Callback received"
        })

    except Exception as e:
        print("M-Pesa callback error:", str(e))
        return JsonResponse({
            "ResultCode": 1,
            "ResultDesc": "Error"
        })


@login_required
def paypal_success(request):
    """PayPal success callback"""
    transaction_id = request.GET.get('transaction_id')
    payment_id = request.GET.get('paymentId')
    payer_id = request.GET.get('PayerID')

    if transaction_id:
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'COMPLETED'
            transaction.gateway_transaction_id = payment_id or payer_id
            transaction.save()

            # Update wallet
            try:
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.balance += transaction.amount
                wallet.save()
            except:
                pass

            messages.success(request, 'PayPal payment completed successfully!')
        except Transaction.DoesNotExist:
            messages.error(request, 'Transaction not found')

    return redirect('transactions')


@login_required
def paypal_cancel(request):
    """PayPal cancellation callback"""
    transaction_id = request.GET.get('transaction_id')

    if transaction_id:
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'CANCELLED'
            transaction.save()
            messages.warning(request, 'PayPal payment was cancelled.')
        except Transaction.DoesNotExist:
            pass

    return redirect('deposit')


@login_required
def alipay_callback(request):
    """Alipay callback"""
    transaction_id = request.GET.get('transaction_id')
    trade_status = request.GET.get('trade_status')

    if transaction_id and trade_status == 'TRADE_SUCCESS':
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, user=request.user)
            transaction.status = 'COMPLETED'
            transaction.save()

            # Update wallet
            try:
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.balance += transaction.amount
                wallet.save()
            except:
                pass

            messages.success(request, 'Alipay payment completed successfully!')
        except Transaction.DoesNotExist:
            messages.error(request, 'Transaction not found')

    return redirect('deposit')


@csrf_exempt
def stripe_webhook(request):
    """Stripe webhook handler"""
    if request.method == 'POST':
        try:
            # For testing, you can use a simple response
            # In production, verify Stripe signature
            data = json.loads(request.body)
            event_type = data.get('type')

            if event_type == 'payment_intent.succeeded':
                payment_intent = data.get('data', {}).get('object', {})
                payment_intent_id = payment_intent.get('id')

                if payment_intent_id:
                    try:
                        transaction = Transaction.objects.get(
                            gateway_transaction_id=payment_intent_id,
                            status='PENDING'
                        )
                        transaction.status = 'COMPLETED'
                        transaction.save()

                        # Update wallet
                        try:
                            wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                            wallet.balance += transaction.amount
                            wallet.save()
                        except:
                            pass

                    except Transaction.DoesNotExist:
                        pass

            return JsonResponse({'status': 'success'})

        except Exception as e:
            print("Stripe webhook error:", str(e))
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return HttpResponse(status=400)


# ==================== UTILITY VIEWS ====================

@login_required
def wallet_balance(request):
    """Get user wallet balance"""
    try:
        wallet = Wallet.objects.get(user=request.user)
        balance = wallet.balance
        currency = wallet.currency
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(user=request.user)
        balance = 0
        currency = 'USD'

    return JsonResponse({
        'balance': float(balance),
        'currency': currency,
        'user': request.user.username
    })


@login_required
def retry_transaction(request, transaction_id):
    """Retry a failed transaction"""
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

    if transaction.status in ['FAILED', 'CANCELLED']:
        # Create a new transaction based on the old one
        new_transaction = Transaction.objects.create(
            user=request.user,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.currency,
            payment_method=transaction.payment_method,
            status='PENDING',
            metadata={'retry_of': str(transaction.transaction_id)}
        )

        messages.success(request, 'Transaction retry initiated!')
        return redirect('transactions')

    messages.error(request, 'Cannot retry this transaction')
    return redirect('transactions')


# ==================== ADDITIONAL API VIEWS ====================

@login_required
def api_transactions_list(request):
    """API endpoint for transactions list"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]

    data = {
        'transactions': [
            {
                'id': str(txn.transaction_id),
                'reference': txn.payment_reference or '',
                'type': txn.transaction_type,
                'amount': float(txn.amount),
                'currency': txn.currency,
                'payment_method': txn.payment_method,
                'status': txn.status,
                'created_at': txn.created_at.isoformat(),
                'formatted_amount': f"{txn.currency} {txn.amount:.2f}",
            }
            for txn in transactions
        ]
    }

    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
def verify_payment(request):
    """Verify payment status"""
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if transaction_id:
            try:
                transaction = Transaction.objects.get(transaction_id=transaction_id)
                return JsonResponse({
                    'success': True,
                    'status': transaction.status,
                    'amount': float(transaction.amount),
                    'currency': transaction.currency
                })
            except Transaction.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Transaction not found'
                }, status=404)

        return JsonResponse({
            'success': False,
            'error': 'Transaction ID required'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== KEEP EXISTING VIEWS ====================

@login_required
def deposit_funds(request):
    """Alternative deposit view - keep for compatibility"""
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            try:
                # Create transaction record
                transaction = Transaction.objects.create(
                    user=request.user,
                    transaction_id=f"DEP{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}",
                    transaction_type='DEPOSIT',
                    amount=form.cleaned_data['amount'],
                    currency=form.cleaned_data['currency'],
                    payment_method=form.cleaned_data['payment_method'],
                    status='COMPLETED',
                    metadata={
                        'phone_number': form.cleaned_data.get('phone_number'),
                        'card_last_four': form.cleaned_data.get('card_number', '')[-4:] if form.cleaned_data.get(
                            'card_number') else None
                    }
                )

                # Update wallet
                try:
                    wallet, created = Wallet.objects.get_or_create(
                        user=request.user,
                        defaults={'balance': Decimal('0'), 'currency': transaction.currency}
                    )
                    wallet.balance += transaction.amount
                    wallet.save()
                except:
                    pass

                messages.success(request, f'Deposit of {transaction.amount} {transaction.currency} completed!')
                return redirect('transactions')

            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    else:
        form = DepositForm()

    return render(request, 'polls/deposit.html', {'form': form})


@login_required
def transaction_history(request):
    """Alias for transactions view"""
    return transactions(request)


# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.urls import reverse
from decimal import Decimal
import json
import random
from datetime import datetime, timedelta
from .models import Transaction, Wallet


@login_required
def deposit(request):
    """Render deposit page"""
    # Don't pass a form variable if you're not using Django forms
    return render(request, "polls/deposit.html", {})


@login_required
@require_POST
def process_deposit(request):
    """Process deposit request"""
    try:
        # Get form data
        data = request.POST

        # Validate required fields
        currency = data.get('currency')
        payment_method = data.get('payment_method')
        terms_accepted = data.get('terms_accepted')
        final_amount = data.get('final_amount')

        if not all([currency, payment_method, terms_accepted, final_amount]):
            messages.error(request, "Please fill all required fields")
            return redirect('deposit')

        # Get amount
        try:
            amount = Decimal(final_amount)
        except:
            messages.error(request, "Invalid amount")
            return redirect('deposit')

        # Validate amount
        if amount < Decimal('1') or amount > Decimal('10000'):
            messages.error(request, "Amount must be between 1 and 10,000")
            return redirect('deposit')

        # Generate unique transaction ID
        transaction_id = f"DEP{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

        # Create transaction record
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_id=transaction_id,
            transaction_type='DEPOSIT',
            amount=amount,
            currency=currency,
            status='PENDING',
            payment_method=payment_method,
            payment_reference=f"REF{int(timezone.now().timestamp())}"
        )

        # Add metadata based on payment method
        metadata = {}

        if payment_method == 'mpesa':
            phone = data.get('mpesa_phone')
            if phone:
                metadata['phone_number'] = phone
                metadata['provider'] = 'M-Pesa'
                metadata['country'] = 'Kenya'
        elif payment_method == 'card':
            card_number = data.get('card_number', '')
            card_last_four = card_number[-4:] if len(card_number) >= 4 else '****'
            metadata['card_last_four'] = card_last_four
            metadata['card_type'] = 'visa' if card_number.startswith('4') else 'mastercard'
            metadata['card_name'] = data.get('card_name', '')
            metadata['provider'] = 'Card Payment'
        elif payment_method == 'paypal':
            metadata['provider'] = 'PayPal'
            metadata['gateway'] = 'PayPal'
        elif payment_method == 'alipay':
            metadata['provider'] = 'Alipay'
            metadata['gateway'] = 'Alipay'

        # Save metadata
        if metadata:
            transaction.metadata = metadata
            transaction.save()

        # For demo purposes, mark as completed immediately
        # In production, you would integrate with actual payment gateway
        transaction.status = 'COMPLETED'
        transaction.save()

        # Update user wallet balance
        try:
            wallet, created = Wallet.objects.get_or_create(
                user=request.user,
                defaults={'balance': 0, 'currency': currency}
            )
            wallet.balance += amount
            wallet.save()
        except Exception as e:
            print(f"Error updating wallet: {e}")

        messages.success(request, f"Deposit of {currency}{amount:.2f} completed successfully!")

        # Redirect to transaction status page
        return redirect('transaction_status', transaction_id=transaction.transaction_id)

    except Exception as e:
        print(f"Error in process_deposit: {e}")
        messages.error(request, f"Error processing deposit: {str(e)}")
        return redirect('deposit')


def calculate_transaction_fee(amount, currency, payment_method):
    """Calculate transaction fee based on payment method and currency"""
    fee = Decimal('0')

    if payment_method == 'card':
        # 2.9% + fixed fee
        fee = (amount * Decimal('0.029')) + (Decimal('30') if currency == 'KES' else Decimal('0.30'))
    elif payment_method == 'paypal':
        # 2.9% fee
        fee = amount * Decimal('0.029')
    elif payment_method == 'mpesa':
        # 1% fee, max 100 KES
        fee = min(amount * Decimal('0.01'), Decimal('100'))
    elif payment_method == 'alipay':
        # 1.5% fee
        fee = amount * Decimal('0.015')

    return fee.quantize(Decimal('0.01'))


@login_required
def transaction_status(request, transaction_id):
    """Show transaction status page"""
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

    context = {
        'transaction': transaction,
        'status_message': get_status_message(transaction.status),
        'estimated_completion': timezone.now() + timedelta(minutes=5) if transaction.status == 'PENDING' else None
    }

    return render(request, "polls/transaction_status.html", context)


def get_status_message(status):
    """Get user-friendly status message"""
    messages = {
        'PENDING': 'Your payment is being processed. This may take a few moments.',
        'COMPLETED': 'Payment completed successfully! Funds have been added to your account.',
        'FAILED': 'Payment failed. Please try again or contact support.',
        'CANCELLED': 'Payment was cancelled.',
        'PROCESSING': 'Payment is currently being processed.'
    }
    return messages.get(status, 'Payment status unknown.')


@login_required
def transactions(request):
    """View all transactions"""
    user_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

    # Calculate stats
    total_amount_result = user_transactions.filter(status='COMPLETED').aggregate(
        total=Sum('amount')
    )
    total_amount = total_amount_result['total'] or Decimal('0')

    deposit_count = user_transactions.filter(
        transaction_type='DEPOSIT',
        status='COMPLETED'
    ).count()

    # Success rate
    total_completed = user_transactions.filter(status='COMPLETED').count()
    total_all = user_transactions.count()
    success_rate = round((total_completed / total_all * 100), 2) if total_all > 0 else 100

    context = {
        'transactions': user_transactions,
        'total_amount': f"{total_amount:.2f}",
        'deposit_count': deposit_count,
        'success_rate': success_rate,
    }

    return render(request, "polls/transactions.html", context)


@login_required
@require_GET
def api_transactions_live(request):
    """API endpoint for live transaction updates"""
    last_update = request.GET.get('last_update')

    try:
        if last_update:
            try:
                last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                new_transactions = Transaction.objects.filter(
                    user=request.user,
                    updated_at__gt=last_update_time
                ).order_by('-created_at')
            except:
                new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:10]
        else:
            new_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:10]

        # Serialize transactions
        transactions_data = []
        for txn in new_transactions:
            transactions_data.append({
                'id': txn.id,
                'transaction_id': txn.transaction_id,
                'transaction_type': txn.transaction_type,
                'amount': str(txn.amount),
                'currency': txn.currency,
                'status': txn.status.lower(),
                'payment_method': txn.payment_method,
                'payment_reference': txn.payment_reference,
                'metadata': txn.metadata or {},
                'created_at': txn.created_at.isoformat(),
                'updated_at': txn.updated_at.isoformat(),
            })

        return JsonResponse({
            'success': True,
            'transactions': transactions_data,
            'last_update': timezone.now().isoformat(),
            'stats': {
                'total_deposits': Transaction.objects.filter(
                    user=request.user,
                    transaction_type='DEPOSIT',
                    status='COMPLETED'
                ).count(),
                'total_amount': str(Transaction.objects.filter(
                    user=request.user,
                    status='COMPLETED'
                ).aggregate(total=Sum('amount'))['total'] or '0'),
            }
        })
    except Exception as e:
        print(f"Error in api_transactions_live: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'transactions': [],
            'last_update': timezone.now().isoformat()
        })


@login_required
@require_GET
def api_transaction_details(request, transaction_id):
    """API endpoint for transaction details"""
    try:
        transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

        return JsonResponse({
            'success': True,
            'transaction': {
                'transaction_id': transaction.transaction_id,
                'transaction_type': transaction.transaction_type,
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'status': transaction.status.lower(),
                'payment_method': transaction.payment_method,
                'payment_reference': transaction.payment_reference,
                'metadata': transaction.metadata or {},
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'user_email': request.user.email,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def api_transaction_retry(request, transaction_id):
    """API endpoint to retry a failed transaction"""
    try:
        transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

        if transaction.status != 'FAILED':
            return JsonResponse({
                'success': False,
                'error': 'Only failed transactions can be retried'
            })

        # Create a new transaction as retry
        new_transaction = Transaction.objects.create(
            user=request.user,
            transaction_id=f"RETRY{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}",
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.currency,
            status='PENDING',
            payment_method=transaction.payment_method,
            payment_reference=f"RETRY{int(timezone.now().timestamp())}",
            metadata=transaction.metadata
        )

        return JsonResponse({
            'success': True,
            'message': 'Transaction retry initiated',
            'new_transaction_id': new_transaction.transaction_id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_GET
def api_transaction_receipt(request, transaction_id):
    """Generate receipt for transaction"""
    try:
        transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)

        return JsonResponse({
            'success': True,
            'receipt': {
                'transaction_id': transaction.transaction_id,
                'date': transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'amount': f"{transaction.currency}{transaction.amount:.2f}",
                'status': transaction.status,
                'payment_method': transaction.payment_method,
                'user': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Transaction


@login_required
def transactions(request):
    """Display user transactions with filtering options"""
    # Get filter parameters
    transaction_type = request.GET.get('type', 'all')
    status = request.GET.get('status', 'all')
    timeframe = request.GET.get('timeframe', 'all')
    search = request.GET.get('search', '')

    # Start with user's transactions
    transactions = Transaction.objects.filter(
        Q(user=request.user) | Q(from_user=request.user) | Q(to_user=request.user)
    ).distinct().order_by('-created_at')

    # Apply type filter - CORRECTED: use 'txn_type' instead of 'transaction_type'
    if transaction_type != 'all':
        transactions = transactions.filter(txn_type=transaction_type)

    # Apply status filter
    if status != 'all':
        transactions = transactions.filter(status=status)

    # Apply timeframe filter
    if timeframe != 'all':
        from django.utils import timezone
        from datetime import timedelta

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

    # Apply search filter
    if search:
        transactions = transactions.filter(
            Q(transaction_id__icontains=search) |
            Q(description__icontains=search) |
            Q(reference__icontains=search)
        )

    # Calculate statistics
    total_transactions = transactions.count()
    total_deposits = Transaction.objects.filter(
        user=request.user,
        txn_type='deposit',  # CORRECTED: use 'txn_type' instead of 'transaction_type'
        status='completed'
    ).count()
    total_withdrawals = Transaction.objects.filter(
        user=request.user,
        txn_type='withdrawal',  # CORRECTED: use 'txn_type' instead of 'transaction_type'
        status='completed'
    ).count()
    total_transfers = Transaction.objects.filter(
        user=request.user,
        txn_type='transfer',  # CORRECTED: use 'txn_type' instead of 'transaction_type'
        status='completed'
    ).count()

    # Get recent transactions for the stats
    recent_transactions = transactions[:10]

    context = {
        'transactions': transactions,
        'recent_transactions': recent_transactions,
        'total_transactions': total_transactions,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'total_transfers': total_transfers,
        'current_filter': {
            'type': transaction_type,
            'status': status,
            'timeframe': timeframe,
            'search': search
        },
        'user': request.user,
        'active_page': 'transactions'
    }

    return render(request, 'polls/transactions.html', context)

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def admin_dashboard(request):
    return render(request, 'polls/dashboard.html')


from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect


def custom_login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect to a success page or next parameter
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'polls/login.html', {'form': form})


#neww code

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from .models import SocialPost, SocialComment, ChatRoom, ChatMessage, Notification
from .forms import PostForm, CommentForm
from django.contrib.auth.models import User
import json


@login_required
def interactions_home(request):
    """Main interactions page showing posts feed"""
    # Get all posts from users the current user follows
    following_users = request.user.profile.following.all()
    all_users = list(following_users) + [request.user]

    posts = Post.objects.filter(user__in=all_users).order_by('-created_at')

    # Get suggested users to follow
    suggested_users = User.objects.exclude(
        Q(id=request.user.id) |
        Q(id__in=following_users.values_list('id', flat=True))
    )[:5]

    # Get unread notifications count
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    context = {
        'posts': posts,
        'suggested_users': suggested_users,
        'unread_notifications': unread_notifications,
        'post_form': PostForm(),
    }
    return render(request, 'interactions/home.html', context)


@login_required
def create_post(request):
    """Create a new post"""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.save()
            return JsonResponse({'success': True, 'post_id': post.id})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def like_post(request, post_id):
    """Like/Unlike a post"""
    post = get_object_or_404(Post, id=post_id)

    if request.user in post.likes.all():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True

        # Create notification if not liking own post
        if request.user != post.user:
            Notification.objects.create(
                user=post.user,
                sender=request.user,
                notification_type='like',
                post=post
            )

    return JsonResponse({
        'success': True,
        'liked': liked,
        'total_likes': post.total_likes()
    })


@login_required
def save_post(request, post_id):
    """Save/Unsave a post"""
    post = get_object_or_404(Post, id=post_id)

    if request.user in post.saves.all():
        post.saves.remove(request.user)
        saved = False
    else:
        post.saves.add(request.user)
        saved = True

    return JsonResponse({
        'success': True,
        'saved': saved
    })


@login_required
def add_comment(request, post_id):
    """Add a comment to a post"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content')

        if content:
            comment = Comment.objects.create(
                post=post,
                user=request.user,
                content=content
            )

            # Create notification if not commenting on own post
            if request.user != post.user:
                Notification.objects.create(
                    user=post.user,
                    sender=request.user,
                    notification_type='comment',
                    post=post,
                    comment=comment
                )

            return JsonResponse({
                'success': True,
                'comment_id': comment.id,
                'user': comment.user.username,
                'content': comment.content,
                'created_at': comment.created_at.strftime('%b %d, %Y %I:%M %p'),
                'total_comments': post.total_comments()
            })

    return JsonResponse({'success': False})


@login_required
def get_comments(request, post_id):
    """Get all comments for a post"""
    post = get_object_or_404(Post, id=post_id)
    comments = post.comments.all().order_by('-created_at')[:20]

    comments_data = []
    for comment in comments:
        comments_data.append({
            'id': comment.id,
            'user': comment.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%b %d, %Y %I:%M %p'),
            'user_avatar': comment.user.profile.get_avatar_url() if hasattr(comment.user, 'profile') else ''
        })

    return JsonResponse({'success': True, 'comments': comments_data})


@login_required
def chat_rooms(request):
    """Get all chat rooms for the user"""
    rooms = ChatRoom.objects.filter(participants=request.user).order_by('-updated_at')

    rooms_data = []
    for room in rooms:
        last_message = room.messages.last()
        other_participants = room.participants.exclude(id=request.user.id)

        rooms_data.append({
            'id': room.id,
            'is_group': room.is_group,
            'name': room.group_name if room.is_group else other_participants.first().username,
            'last_message': last_message.content if last_message else 'No messages yet',
            'last_message_time': last_message.created_at.strftime('%I:%M %p') if last_message else '',
            'unread_count': room.messages.filter(is_read=False).exclude(sender=request.user).count(),
            'participants': [p.username for p in other_participants]
        })

    return JsonResponse({'success': True, 'rooms': rooms_data})


@login_required
def chat_messages(request, room_id):
    """Get messages for a specific chat room"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)

    # Mark messages as read
    room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages = room.messages.all().order_by('created_at')[:50]

    messages_data = []
    for message in messages:
        messages_data.append({
            'id': message.id,
            'sender': message.sender.username,
            'content': message.content,
            'image': message.image.url if message.image else None,
            'is_own': message.sender == request.user,
            'time': message.created_at.strftime('%I:%M %p'),
            'date': message.created_at.strftime('%b %d')
        })

    return JsonResponse({'success': True, 'messages': messages_data})


@login_required
def send_message(request, room_id):
    """Send a message in a chat room"""
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
        content = request.POST.get('content')
        image = request.FILES.get('image')

        if content or image:
            message = ChatMessage.objects.create(
                room=room,
                sender=request.user,
                content=content or '',
                image=image
            )

            room.updated_at = timezone.now()
            room.save()

            # Create notification for other participants
            for participant in room.participants.exclude(id=request.user.id):
                Notification.objects.create(
                    user=participant,
                    sender=request.user,
                    notification_type='message',
                )

            return JsonResponse({
                'success': True,
                'message_id': message.id,
                'content': message.content,
                'image': message.image.url if message.image else None,
                'time': message.created_at.strftime('%I:%M %p')
            })

    return JsonResponse({'success': False})


@login_required
def create_chat_room(request, username):
    """Create or get existing chat room with a user"""
    other_user = get_object_or_404(User, username=username)

    # Check if room already exists
    room = ChatRoom.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).filter(is_group=False).first()

    if not room:
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(request.user, other_user)

    return JsonResponse({'success': True, 'room_id': room.id})

def get_notification_message(notification):
    """Generate notification message based on type"""
    if notification.notification_type == 'like':
        return f"{notification.sender.username} liked your post"
    elif notification.notification_type == 'comment':
        return f"{notification.sender.username} commented on your post"
    elif notification.notification_type == 'message':
        return f"{notification.sender.username} sent you a message"
    elif notification.notification_type == 'trade_alert':
        return f"Trade alert from {notification.sender.username}"
    return "New notification"


@login_required
def explore_posts(request):
    """Explore page showing trending trading posts"""
    # Get trending posts (most liked in last 7 days)
    from datetime import timedelta
    from django.utils import timezone

    week_ago = timezone.now() - timedelta(days=7)
    trending_posts = Post.objects.filter(
        created_at__gte=week_ago
    ).order_by('-likes__count', '-views')[:20]

    # Get popular trading symbols
    popular_symbols = Post.objects.exclude(symbol__isnull=True).values('symbol').annotate(
        count=models.Count('symbol')
    ).order_by('-count')[:10]

    return render(request, 'interactions/explore.html', {
        'trending_posts': trending_posts,
        'popular_symbols': popular_symbols
    })


@login_required
def saved_posts(request):
    """View saved posts"""
    saved_posts = request.user.saved_posts.all()
    return render(request, 'interactions/saved.html', {'posts': saved_posts})




#RECENT VIEWS
#DFGH

# My_app/views.py - Add these community views
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Case, When, IntegerField
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from .models import (
    SocialPost, SocialPostLike, SocialComment, FollowRelationship,
    Profile, Notification, ChatMessage, ChatRoom, ChatRoomMember
)
from .forms import PostForm, CommentForm
import json


@login_required
def community_feed(request):
    """Main community feed showing posts from followed users and trending posts"""
    user = request.user
    profile = user.profile

    # Get posts from users you follow
    following_users = User.objects.filter(followers__follower=user)

    # Get public posts and posts from followed users
    posts = SocialPost.objects.filter(
        Q(visibility='public') |
        Q(author__in=following_users) |
        Q(author=user)
    ).filter(
        is_active=True,
        post_status='published'
    ).select_related('author__profile').prefetch_related('likes', 'comments').order_by('-created_at')

    # Apply pagination
    paginator = Paginator(posts, 10)  # 10 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get suggested users to follow
    suggested_users = User.objects.exclude(
        Q(id=user.id) |
        Q(id__in=following_users)
    ).annotate(
        post_count=Count('social_posts', filter=Q(social_posts__is_active=True))
    ).filter(
        post_count__gt=0
    ).order_by('-profile__reputation_score')[:5]

    # Get trending posts (most liked in last 7 days)
    week_ago = timezone.now() - timezone.timedelta(days=7)
    trending_posts = SocialPost.objects.filter(
        created_at__gte=week_ago,
        is_active=True,
        post_status='published',
        visibility='public'
    ).annotate(
        like_count=Count('likes', filter=Q(likes__is_active=True))
    ).order_by('-like_count', '-views_count')[:5]

    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=user, is_read=False).count()

    # Get unread messages count
    unread_messages = ChatMessage.objects.filter(
        receiver=user,
        is_read=False
    ).count()

    context = {
        'page_obj': page_obj,
        'suggested_users': suggested_users,
        'trending_posts': trending_posts,
        'unread_notifications': unread_notifications,
        'unread_messages': unread_messages,
        'profile': profile,
        'form': PostForm() if request.method == 'GET' else None,
    }

    return render(request, 'My_app/community/feed.html', context)


@login_required
def create_post(request):
    """Create a new post"""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()

            # Handle mentions
            content = post.content
            mentions = extract_mentions(content)
            for username in mentions:
                try:
                    mentioned_user = User.objects.get(username=username[1:])  # Remove @
                    post.mentioned_users.add(mentioned_user)

                    # Create notification
                    Notification.objects.create(
                        user=mentioned_user,
                        notification_type='mention',
                        title=f"You were mentioned by {request.user.username}",
                        message=f"{request.user.username} mentioned you in a post",
                        related_post=post
                    )
                except User.DoesNotExist:
                    pass

            messages.success(request, 'Post created successfully!')
            return redirect('post_detail', post_id=post.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PostForm()

    return render(request, 'My_app/community/create_post.html', {'form': form})


@login_required
def post_detail(request, post_id):
    """View a specific post with comments"""
    post = get_object_or_404(SocialPost, id=post_id, is_active=True)

    # Check if user can view this post
    if not post.can_view(request.user):
        messages.error(request, 'You do not have permission to view this post.')
        return redirect('community_feed')

    # Increment view count
    post.increment_views()

    # Get comments
    comments = post.comments.filter(is_active=True, parent_comment__isnull=True).order_by('created_at')

    # Get related posts
    related_posts = SocialPost.objects.filter(
        author=post.author,
        is_active=True,
        post_status='published'
    ).exclude(id=post.id).order_by('-created_at')[:3]

    # Check if user liked this post
    user_liked = post.likes.filter(user=request.user, is_active=True).exists()

    context = {
        'post': post,
        'comments': comments,
        'related_posts': related_posts,
        'user_liked': user_liked,
        'comment_form': CommentForm(),
        'profile': request.user.profile,
    }

    return render(request, 'My_app/community/post_detail.html', context)


@login_required
def toggle_like(request, post_id):
    """Like or unlike a post"""
    post = get_object_or_404(SocialPost, id=post_id, is_active=True)

    # Check if user already liked the post
    like, created = SocialPostLike.objects.get_or_create(
        post=post,
        user=request.user
    )

    if not created:
        # Toggle like status
        like.is_active = not like.is_active
        like.save()

    # Create notification if liked
    if like.is_active and post.author != request.user:
        Notification.objects.create(
            user=post.author,
            notification_type='post_like',
            title=f"{request.user.username} liked your post",
            message=f"{request.user.username} liked your post: '{post.get_summary(50)}'",
            related_post=post,
            related_user=request.user
        )

    return JsonResponse({
        'success': True,
        'likes_count': post.likes.filter(is_active=True).count(),
        'is_liked': like.is_active
    })


@login_required
def add_comment(request, post_id):
    """Add a comment to a post"""
    post = get_object_or_404(SocialPost, id=post_id, is_active=True)

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user

            # Handle parent comment for replies
            parent_id = request.POST.get('parent_comment')
            if parent_id:
                try:
                    parent_comment = SocialComment.objects.get(id=parent_id)
                    comment.parent_comment = parent_comment
                except SocialComment.DoesNotExist:
                    pass

            comment.save()

            # Handle mentions in comment
            content = comment.content
            mentions = extract_mentions(content)
            for username in mentions:
                try:
                    mentioned_user = User.objects.get(username=username[1:])
                    comment.mentioned_users.add(mentioned_user)

                    # Create notification
                    Notification.objects.create(
                        user=mentioned_user,
                        notification_type='mention',
                        title=f"You were mentioned by {request.user.username}",
                        message=f"{request.user.username} mentioned you in a comment",
                        related_post=post,
                        related_comment=comment
                    )
                except User.DoesNotExist:
                    pass

            # Notify post author if it's not the commenter
            if post.author != request.user:
                Notification.objects.create(
                    user=post.author,
                    notification_type='post_comment',
                    title=f"{request.user.username} commented on your post",
                    message=f"{request.user.username} commented on your post",
                    related_post=post,
                    related_comment=comment,
                    related_user=request.user
                )

            messages.success(request, 'Comment added successfully!')
        else:
            messages.error(request, 'Error adding comment.')

    return redirect('post_detail', post_id=post_id)


@login_required
def user_profile(request, username):
    """View user profile"""
    user = get_object_or_404(User, username=username)
    profile = user.profile

    # Check if current user can view this profile
    if not profile.can_view_profile(request.user):
        messages.error(request, 'This profile is private.')
        return redirect('community_feed')

    # Get user's posts
    posts = SocialPost.objects.filter(
        author=user,
        is_active=True,
        post_status='published'
    ).order_by('-created_at')

    # Check if current user is following this user
    is_following = FollowRelationship.objects.filter(
        follower=request.user,
        followed=user
    ).exists()

    # Get user stats
    user_stats = {
        'posts_count': posts.count(),
        'followers_count': profile.followers_count,
        'following_count': profile.following_count,
        'likes_received': profile.total_likes_received,
    }

    context = {
        'profile_user': user,
        'profile': profile,
        'posts': posts[:9],  # Show 9 most recent posts
        'is_following': is_following,
        'user_stats': user_stats,
        'can_edit': request.user == user,
    }

    return render(request, 'My_app/community/profile1.html', context)


@login_required
def toggle_follow(request, username):
    """Follow or unfollow a user"""
    user_to_follow = get_object_or_404(User, username=username)

    if request.user == user_to_follow:
        return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    follow, created = FollowRelationship.objects.get_or_create(
        follower=request.user,
        followed=user_to_follow
    )

    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True

        # Create notification
        Notification.objects.create(
            user=user_to_follow,
            notification_type='new_follower',
            title=f"{request.user.username} started following you",
            message=f"{request.user.username} is now following you",
            related_user=request.user
        )

    # Update profile stats
    request.user.profile.update_community_stats()
    user_to_follow.profile.update_community_stats()

    return JsonResponse({
        'success': True,
        'is_following': is_following,
        'followers_count': user_to_follow.profile.followers_count
    })



@login_required
def direct_chat(request, username):
    """Direct message chat with a specific user"""
    other_user = get_object_or_404(User, username=username)

    # Get or create chat room
    chat_room = ChatRoom.objects.filter(
        members=request.user
    ).filter(
        members=other_user
    ).filter(is_group=False).first()

    if not chat_room:
        chat_room = ChatRoom.objects.create(is_group=False)
        chat_room.members.add(request.user, other_user)

    # Get messages
    messages = ChatMessage.objects.filter(
        chat_room=chat_room
    ).order_by('created_at')

    # Mark messages as read
    messages.filter(is_read=False, sender=other_user).update(is_read=True)

    context = {
        'other_user': other_user,
        'chat_room': chat_room,
        'messages': messages,
    }
    return render(request, 'My_app/community/direct_chat.html', context)


@login_required
def group_chat_view(request, room_id):
    """View for a specific group chat room"""
    group_chat = get_object_or_404(ChatRoom, id=room_id, is_group=True)

    # Check if user is a member
    if request.user not in group_chat.members.all():
        return HttpResponseForbidden("You don't have access to this group chat.")

    # Get messages
    messages = ChatMessage.objects.filter(
        room=group_chat
    ).order_by('created_at')

    # Mark user's unread messages as read
    messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    context = {
        'group_chat': group_chat,
        'messages': messages,
        'is_group_admin': group_chat.created_by == request.user,
    }
    return render(request, 'My_app/community/group_chat.html', context)


@login_required
def create_group_chat_view(request):
    """Create a new group chat room"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        member_ids = request.POST.getlist('members')

        if name:
            group_chat = ChatRoom.objects.create(
                name=name,
                description=description,
                is_group=True,
                created_by=request.user
            )

            # Add creator
            group_chat.members.add(request.user)

            # Add selected members
            for member_id in member_ids:
                try:
                    member = User.objects.get(id=member_id)
                    group_chat.members.add(member)
                except User.DoesNotExist:
                    pass

            # Send welcome message
            ChatMessage.objects.create(
                room=group_chat,
                sender=request.user,
                content=f"Group chat '{group_chat.name}' created",
                is_system=True
            )

            messages.success(request, f'Group chat "{group_chat.name}" created!')
            return redirect('group_chat_view', room_id=group_chat.id)

    # Get users that current user follows for suggestions
    following = FollowRelationship.objects.filter(
        follower=request.user
    ).values_list('followed', flat=True)

    suggested_members = User.objects.filter(id__in=following)

    context = {
        'suggested_members': suggested_members,
    }
    return render(request, 'My_app/community/create_group_chat.html', context)


@login_required
def messages_conversation(request, username):
    """Alternative name for direct_chat"""
    return direct_chat(request, username)


# Keep the existing API endpoints (they should work fine)
@login_required
def api_send_message(request):
    """API endpoint to send a message"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_username = data.get('receiver')
            content = data.get('content')
            room_id = data.get('room_id')

            if room_id:
                # Send to group chat
                room = get_object_or_404(ChatRoom, id=room_id)
                if request.user not in room.members.all():
                    return JsonResponse({'success': False, 'error': 'Not a member'})

                message = ChatMessage.objects.create(
                    room=room,
                    sender=request.user,
                    content=content
                )

                receiver_data = {
                    'type': 'group',
                    'name': room.name
                }
            elif receiver_username:
                # Send direct message
                receiver = get_object_or_404(User, username=receiver_username)

                # Get or create chat room
                chat_room = ChatRoom.objects.filter(
                    members=request.user
                ).filter(
                    members=receiver
                ).filter(is_group=False).first()

                if not chat_room:
                    chat_room = ChatRoom.objects.create(is_group=False)
                    chat_room.members.add(request.user, receiver)

                message = ChatMessage.objects.create(
                    room=chat_room,
                    sender=request.user,
                    receiver=receiver,
                    content=content
                )

                receiver_data = {
                    'type': 'user',
                    'username': receiver.username,
                    'display_name': receiver.get_full_name() or receiver.username
                }
            else:
                return JsonResponse({'success': False, 'error': 'No recipient specified'})

            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'sender': message.sender.username,
                    'receiver': receiver_data,
                    'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_read': message.is_read
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# ... (the rest of the file remains the same) ...


# views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Message


@login_required
def messages_view(request, username=None):
    """Handle both messages list and conversation detail"""
    user = request.user

    if username:
        # This is a conversation with a specific user
        other_user = get_object_or_404(User, username=username)

        # Get messages between current user and the other user
        messages = Message.objects.filter(
            (models.Q(sender=user, recipient=other_user) |
             models.Q(sender=other_user, recipient=user))
        ).order_by('timestamp')

        # Mark messages as read
        messages.filter(recipient=user, is_read=False).update(is_read=True)

        context = {
            'active_conversation': other_user,
            'messages': messages,
            'other_user': other_user,
        }

        return render(request, 'My_app/community/chat_detail.html', context)

    else:
        # This is the messages list/inbox
        # Get all conversations for the current user
        sent_messages = Message.objects.filter(sender=user).values('recipient').distinct()
        received_messages = Message.objects.filter(recipient=user).values('sender').distinct()

        # Combine and get unique users
        user_ids = set()
        user_ids.update(msg['recipient'] for msg in sent_messages)
        user_ids.update(msg['sender'] for msg in received_messages)

        conversations = []
        for user_id in user_ids:
            other_user = User.objects.get(id=user_id)
            last_message = Message.objects.filter(
                (models.Q(sender=user, recipient=other_user) |
                 models.Q(sender=other_user, recipient=user))
            ).order_by('-timestamp').first()

            unread_count = Message.objects.filter(
                sender=other_user,
                recipient=user,
                is_read=False
            ).count()

            conversations.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count,
            })

        # Sort by most recent message
        conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else x['user'].date_joined,
                           reverse=True)

        context = {
            'conversations': conversations,
        }

        return render(request, 'polls/messages.html', context)


# OR keep separate views:

@login_required
def messages_list(request):
    """Display list of conversations"""
    user = request.user

    # Get all unique users the current user has messaged with
    sent_to = User.objects.filter(
        id__in=Message.objects.filter(sender=user).values('recipient')
    ).distinct()

    received_from = User.objects.filter(
        id__in=Message.objects.filter(recipient=user).values('sender')
    ).distinct()

    # Combine and deduplicate
    all_users = (sent_to | received_from).distinct()

    conversations = []
    for other_user in all_users:
        last_message = Message.objects.filter(
            (models.Q(sender=user, recipient=other_user) |
             models.Q(sender=other_user, recipient=user))
        ).order_by('-timestamp').first()

        unread_count = Message.objects.filter(
            sender=other_user,
            recipient=user,
            is_read=False
        ).count()

        conversations.append({
            'user': other_user,
            'last_message': last_message,
            'unread_count': unread_count,
        })

    # Sort by last message time
    conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else x['user'].date_joined,
                       reverse=True)

    return render(request, 'polls/messages.html', {'conversations': conversations})


@login_required
def chat_detail(request, username):
    """Display conversation with a specific user"""
    user = request.user
    other_user = get_object_or_404(User, username=username)

    # Get messages between users
    messages = Message.objects.filter(
        (models.Q(sender=user, recipient=other_user) |
         models.Q(sender=other_user, recipient=user))
    ).order_by('timestamp')

    # Mark messages as read
    messages.filter(recipient=user, is_read=False).update(is_read=True)

    # Handle new message submission
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=user,
                recipient=other_user,
                content=content
            )
            # Redirect to prevent form resubmission
            return redirect('messages_conversation', username=username)

    context = {
        'other_user': other_user,
        'messages': messages,
    }

    return render(request, 'My_app/community/chat_detail.html', context)


@login_required
def notifications1(request):
    """View user notifications"""
    user = request.user
    notifications_list = Notification.objects.filter(user=user).order_by('-created_at')

    # Apply pagination
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'unread_count': notifications_list.filter(is_read=False).count(),
        'profile': user.profile,
    }

    return render(request, 'My_app/community/notifications1.html', context)


@login_required
def mark_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )

    return JsonResponse({'success': True})


@login_required
def search_users(request):
    """Search for users"""
    query = request.GET.get('q', '')

    if query:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(profile__display_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id).select_related('profile')

        posts = SocialPost.objects.filter(
            Q(content__icontains=query) |
            Q(trading_symbol__icontains=query)
        ).filter(
            is_active=True,
            post_status='published',
            visibility='public'
        ).select_related('author__profile')
    else:
        users = User.objects.none()
        posts = SocialPost.objects.none()

    context = {
        'query': query,
        'users': users,
        'posts': posts,
        'profile': request.user.profile,
    }

    return render(request, 'My_app/community/search.html', context)


# API endpoints for AJAX requests
@login_required
def api_like_post(request):
    """API endpoint to like/unlike a post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            post = get_object_or_404(SocialPost, id=post_id)

            # Toggle like
            like, created = SocialPostLike.objects.get_or_create(
                post=post,
                user=request.user
            )

            if not created:
                like.is_active = not like.is_active
                like.save()

            # Create notification if liked
            if like.is_active and post.author != request.user:
                Notification.objects.create(
                    user=post.author,
                    notification_type='post_like',
                    title=f"{request.user.username} liked your post",
                    message=f"{request.user.username} liked your post",
                    related_post=post,
                    related_user=request.user
                )

            return JsonResponse({
                'success': True,
                'likes_count': post.likes.filter(is_active=True).count(),
                'is_liked': like.is_active
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def api_add_comment(request):
    """API endpoint to add a comment"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            content = data.get('content')
            parent_id = data.get('parent_id')

            post = get_object_or_404(SocialPost, id=post_id)

            comment = SocialComment.objects.create(
                post=post,
                author=request.user,
                content=content
            )

            if parent_id:
                try:
                    parent_comment = SocialComment.objects.get(id=parent_id)
                    comment.parent_comment = parent_comment
                    comment.save()
                except SocialComment.DoesNotExist:
                    pass

            # Create HTML for the new comment
            comment_html = f'''
            <div class="comment mb-3" id="comment-{comment.id}">
                <div class="d-flex">
                    <img src="{comment.author.profile.get_avatar_url()}" 
                         class="rounded-circle me-2" 
                         width="32" height="32" 
                         alt="{comment.author.username}">
                    <div class="flex-grow-1">
                        <div class="bg-light rounded p-2">
                            <div class="d-flex justify-content-between">
                                <strong>{comment.author.profile.get_display_name()}</strong>
                                <small class="text-muted">{comment.created_at | timesince} ago</small>
                            </div>
                            <p class="mb-1">{comment.content}</p>
                            <div class="small">
                                <a href="#" class="text-decoration-none me-2 reply-link" 
                                   data-comment-id="{comment.id}">Reply</a>
                                {'' if request.user != comment.author else f'<a href="#" class="text-decoration-none text-danger delete-comment" data-comment-id="{comment.id}">Delete</a>'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''

            return JsonResponse({
                'success': True,
                'comment_html': comment_html,
                'comment_id': comment.id
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def api_follow_user(request):
    """API endpoint to follow/unfollow a user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')

            user_to_follow = get_object_or_404(User, username=username)

            if request.user == user_to_follow:
                return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

            follow, created = FollowRelationship.objects.get_or_create(
                follower=request.user,
                followed=user_to_follow
            )

            if not created:
                follow.delete()
                is_following = False
            else:
                is_following = True

                # Create notification
                Notification.objects.create(
                    user=user_to_follow,
                    notification_type='new_follower',
                    title=f"{request.user.username} started following you",
                    message=f"{request.user.username} is now following you",
                    related_user=request.user
                )

            # Update profile stats
            request.user.profile.update_community_stats()
            user_to_follow.profile.update_community_stats()

            return JsonResponse({
                'success': True,
                'is_following': is_following,
                'followers_count': user_to_follow.profile.followers_count
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def api_send_message(request):
    """API endpoint to send a message"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_username = data.get('receiver')
            message_text = data.get('message')
            chat_room_id = data.get('chat_room_id')

            if receiver_username:
                receiver = get_object_or_404(User, username=receiver_username)
                chat_room = ChatRoom.get_or_create_direct_chat(request.user, receiver)
            elif chat_room_id:
                chat_room = get_object_or_404(ChatRoom, id=chat_room_id)
                if request.user not in chat_room.members.all():
                    return JsonResponse({'error': 'You are not a member of this chat room'}, status=403)
                receiver = None
            else:
                return JsonResponse({'error': 'No receiver or chat room specified'}, status=400)

            message = ChatMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                chat_room=chat_room,
                content=message_text,
                message_type='text'
            )

            # Update chat room last message
            chat_room.update_last_message(message)

            # Increment unread count for other members
            for member in chat_room.members.exclude(id=request.user.id):
                member_membership = ChatRoomMember.objects.filter(
                    chat_room=chat_room,
                    user=member
                ).first()
                if member_membership:
                    member_membership.increment_unread_count()

            return JsonResponse({
                'success': True,
                'message_id': message.id,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'sender_name': request.user.profile.get_display_name(),
                'sender_avatar': request.user.profile.get_avatar_url()
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def api_get_messages(request):
    """API endpoint to get messages for a chat"""
    if request.method == 'GET':
        try:
            chat_room_id = request.GET.get('chat_room_id')
            username = request.GET.get('username')
            last_message_id = request.GET.get('last_message_id')

            if chat_room_id:
                chat_room = get_object_or_404(ChatRoom, id=chat_room_id)
            elif username:
                other_user = get_object_or_404(User, username=username)
                chat_room = ChatRoom.get_or_create_direct_chat(request.user, other_user)
            else:
                return JsonResponse({'error': 'No chat specified'}, status=400)

            # Get messages
            messages_query = ChatMessage.objects.filter(chat_room=chat_room)

            if last_message_id:
                try:
                    last_message = ChatMessage.objects.get(id=last_message_id)
                    messages_query = messages_query.filter(created_at__gt=last_message.created_at)
                except ChatMessage.DoesNotExist:
                    pass

            messages = messages_query.order_by('created_at')

            # Mark messages as read
            unread_messages = messages.filter(is_read=False, sender__in=chat_room.members.exclude(id=request.user.id))
            unread_messages.update(is_read=True, read_at=timezone.now())

            # Mark chat room as read for user
            membership = ChatRoomMember.objects.filter(chat_room=chat_room, user=request.user).first()
            if membership:
                membership.reset_unread_count()

            # Format messages for JSON response
            messages_data = []
            for msg in messages:
                messages_data.append({
                    'id': msg.id,
                    'sender': {
                        'id': msg.sender.id,
                        'username': msg.sender.username,
                        'display_name': msg.sender.profile.get_display_name(),
                        'avatar': msg.sender.profile.get_avatar_url()
                    },
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_read': msg.is_read,
                    'is_file': msg.is_file_message,
                    'attachment_url': msg.attachment.url if msg.attachment else None,
                    'attachment_name': msg.attachment_name
                })

            return JsonResponse({
                'success': True,
                'messages': messages_data,
                'chat_room_id': chat_room.id,
                'chat_room_name': chat_room.display_name
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def api_delete_post(request):
    """API endpoint to delete a post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')

            post = get_object_or_404(SocialPost, id=post_id)

            # Check if user is the author
            if post.author != request.user and not request.user.is_staff:
                return JsonResponse({'error': 'You are not authorized to delete this post'}, status=403)

            # Soft delete (set is_active to False)
            post.is_active = False
            post.save()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


# Helper function to extract mentions from text
def extract_mentions(text):
    """Extract @mentions from text"""
    import re
    return re.findall(r'@(\w+)', text)


# social/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q, Count
import json

@login_required
def explore(request):
    """Explore page - discover content"""
    # Popular posts
    popular_posts = Post.objects.annotate(
        total_likes=Count('likes')
    ).order_by('-total_likes', '-created_at')[:20]

    # Top traders
    top_traders = User.objects.annotate(
        posts_count=Count('posts'),
        followers_count=Count('followers'),
        total_likes=Count('posts__likes')
    ).order_by('-followers_count', '-total_likes')[:10]

    # Trending symbols
    from django.db.models import Count
    trending_symbols = Post.objects.exclude(
        trading_symbol__isnull=True
    ).values('trading_symbol').annotate(
        posts_count=Count('id')
    ).order_by('-posts_count')[:10]

    context = {
        'popular_posts': popular_posts,
        'top_traders': top_traders,
        'trending_symbols': trending_symbols,
    }
    return render(request, 'social/explore.html', context)

# profiles/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Count, Sum
from .models import Profile, FollowRelationship as Follow
from .forms import ProfileForm
import json
# CORRECTED IMPORT - Use your actual model names
from .models import (
    SocialPost as Post,
    SocialComment as Comment,
    SocialPostLike as Like,
    FollowRelationship as Follow,
    ChatMessage as Message,
    Notification,
    # Save model doesn't exist - you'll need to create it or use SocialPostLike
    # For now, you can create a simple Save model or remove it
)

@login_required
def profile1(request, username):
    """User profile page"""
    profile_user = get_object_or_404(User, username=username)

    # Get user stats
    posts_count = profile_user.posts.count()
    followers_count = profile_user.followers.count()
    following_count = profile_user.following.count()
    likes_received = Like.objects.filter(post__author=profile_user).count()

    # Get posts
    posts = profile_user.posts.select_related('author__profile').prefetch_related(
        'likes', 'comments'
    ).order_by('-created_at')

    # Get trade posts
    trade_posts = profile_user.posts.exclude(
        trading_symbol__isnull=True
    ).select_related('author__profile')

    # Check if current user can edit this profile
    can_edit = (request.user == profile_user)
    is_following = False
    if request.user.is_authenticated and not can_edit:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=profile_user
        ).exists()

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'trade_posts': trade_posts,
        'user_stats': {
            'posts_count': posts_count,
            'followers_count': followers_count,
            'following_count': following_count,
            'likes_received': likes_received,
        },
        'can_edit': can_edit,
        'is_following': is_following,
        'has_more_posts': posts.count() > 12,
    }
    return render(request, 'My_app/community/profile.html', context)


@login_required
def follow_user(request):
    """Follow/Unfollow a user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            target_user = get_object_or_404(User, id=user_id)

            if request.user == target_user:
                return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

            follow, created = Follow.objects.get_or_create(
                follower=request.user,
                following=target_user
            )

            if not created:
                follow.delete()
                status = 'unfollowed'
            else:
                status = 'following'

                # Create notification
                Notification.objects.create(
                    user=target_user,
                    notification_type='follow',
                    message=f'{request.user.username} started following you'
                )

            return JsonResponse({
                'status': status,
                'followers_count': target_user.followers.count()
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def profile_update(request):
    """Update profile"""
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)

    context = {'form': form}
    return render(request, 'polls/profile.html', context)

# community/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
# Option 1: Import with aliases
from .models import (
    SocialPost as Post,
    SocialComment as Comment,
    SocialPostLike as Like,
    FollowRelationship as Follow,
    ChatMessage as Message,
    ChatRoom as MessageRoom,
    Notification
)

# Option 2: Or if you added aliases to models.py, keep the original import
#from .models import Post, Comment, Like, Follow, Message, MessageRoom, Notification
#from .forms import PostForm, CommentForm, MessageForm, GroupChatForm

# Simple Form without Model
from django import forms
from django.contrib.auth.models import User


class GroupChatForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter group name'
        }),
        label="Group Name"
    )

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Group description (optional)',
            'rows': 3
        }),
        label="Description"
    )

    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Add Members"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Show all users except the current user
            self.fields['members'].queryset = User.objects.exclude(id=user.id)
# Create Group Chat View
# Create Group Chat View - FIXED VERSION
@login_required
def create_group_chat(request):
    """Create a new group chat room"""

    if request.method == 'POST':
        # Get form data
        group_name = request.POST.get('group_name', '').strip()
        description = request.POST.get('description', '').strip()
        member_ids = request.POST.getlist('members')

        if not group_name:
            messages.error(request, 'Group name is required')
            return redirect('create_group_chat')

        try:
            # Try to create chat using available models
            group_created = False

            # Option 1: If ChatRoom model exists
            try:
                from .models import ChatRoom
                group_chat = ChatRoom.objects.create(
                    name=group_name,
                    description=description,
                    created_by=request.user,
                    is_group=True
                )
                group_chat.members.add(request.user)
                for member_id in member_ids:
                    try:
                        member = User.objects.get(id=member_id)
                        group_chat.members.add(member)
                    except User.DoesNotExist:
                        pass
                group_created = True
            except (ImportError, NameError, AttributeError):
                pass  # ChatRoom model doesn't exist

            # Option 2: If Conversation/Group model exists by another name
            if not group_created:
                try:
                    from .models import Conversation
                    conversation = Conversation.objects.create(
                        name=group_name,
                        created_by=request.user,
                        is_group=True
                    )
                    conversation.participants.add(request.user)
                    for member_id in member_ids:
                        try:
                            member = User.objects.get(id=member_id)
                            conversation.participants.add(member)
                        except User.DoesNotExist:
                            pass
                    group_created = True
                except (ImportError, NameError, AttributeError):
                    pass  # Conversation model doesn't exist

            if group_created:
                messages.success(request, f'Group "{group_name}" created successfully!')
            else:
                messages.info(request, f'Group "{group_name}" concept saved. Chat system needs configuration.')

            return redirect('chat_list')

        except Exception as e:
            messages.error(request, f'Error creating group: {str(e)}')
            return redirect('create_group_chat')

    # GET request - show form
    all_users = User.objects.exclude(id=request.user.id).order_by('username')

    # Get users the current user follows
    following_users = []
    try:
        # CORRECT: Use 'followed' field for users I follow
        following_ids = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
        following_users = User.objects.filter(id__in=following_ids)
    except Exception as e:
        print(f"Debug: Could not get following users: {e}")
        # Try alternative if field names are different
        try:
            # Some systems use 'to_user' or 'target' instead of 'followed'
            if hasattr(Follow, 'to_user'):
                following_ids = Follow.objects.filter(from_user=request.user).values_list('to_user', flat=True)
                following_users = User.objects.filter(id__in=following_ids)
        except:
            pass

    context = {
        'users': all_users,
        'following_users': following_users,
    }
    return render(request, 'My_app/community/create_group_chat.html', context)
# Group Chat View
@login_required
def group_chat(request, room_id):
    """View for a specific group chat room"""
    group_chat = get_object_or_404(MessageRoom.objects.prefetch_related('members'),
                                   id=room_id, is_group=True)

    # Check if user is a member
    if request.user not in group_chat.members.all():
        return HttpResponseForbidden("You don't have access to this group chat.")

    # Get messages for this room
    messages = Message.objects.filter(room=group_chat).select_related(
        'sender__profile'
    ).order_by('created_at')

    # Handle new message
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                room=group_chat,
                sender=request.user,
                content=content
            )
            return redirect('group_chat', room_id=room_id)

    # Mark user's unread messages as read
    Message.objects.filter(
        room=group_chat,
        read=False
    ).exclude(sender=request.user).update(read=True)

    # Get room members info
    members = group_chat.members.select_related('profile').all()

    context = {
        'group_chat': group_chat,
        'messages': messages,
        'members': members,
        'is_group_admin': group_chat.created_by == request.user,
    }
    return render(request, 'My_app/community/group_chat.html', context)


# Edit Post View
@login_required
def edit_post(request, post_id):
    """Edit an existing post"""
    post = get_object_or_404(Post, id=post_id)

    # Check if user owns the post
    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to edit this post.")
        return redirect('post_detail', post_id=post_id)

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated_post = form.save()
            updated_post.edited_at = timezone.now()
            updated_post.save()

            messages.success(request, 'Post updated successfully!')
            return redirect('post_detail', post_id=post.id)
    else:
        form = PostForm(instance=post)

    context = {
        'form': form,
        'post': post,
        'is_edit': True,
    }
    return render(request, 'My_app/community/edit_post.html', context)


# Delete Post View
@login_required
def delete_post(request, post_id):
    """Delete a post"""
    post = get_object_or_404(Post, id=post_id)

    # Check if user owns the post
    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to delete this post.")
        return redirect('post_detail', post_id=post_id)

    if request.method == 'POST':
        post_title = post.title
        post.delete()
        messages.success(request, f'Post "{post_title}" deleted successfully!')
        return redirect('community_feed')

    context = {
        'post': post,
        'post_type': 'post',
    }
    return render(request, 'My_app/community/confirm_delete.html', context)


# Delete Comment View
@login_required
def delete_comment(request, comment_id):
    """Delete a comment"""
    comment = get_object_or_404(Comment.objects.select_related('post', 'author'),
                                id=comment_id)

    # Check if user owns the comment or the post
    can_delete = (
            comment.author == request.user or
            comment.post.author == request.user or
            request.user.is_staff
    )

    if not can_delete:
        messages.error(request, "You don't have permission to delete this comment.")
        return redirect('post_detail', post_id=comment.post.id)

    post_id = comment.post.id

    if request.method == 'POST':
        comment.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('post_detail', post_id=post_id)

    context = {
        'comment': comment,
        'post_type': 'comment',
    }
    return render(request, 'My_app/community/confirm_delete.html', context)


# Following List View
@login_required
def following_list(request):
    """Show list of users that the current user follows"""
    # Get following relationships
    following = Follow.objects.filter(
        follower=request.user
    ).select_related('following__profile').order_by('-created_at')

    # Pagination
    paginator = Paginator(following, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get count
    following_count = following.count()

    context = {
        'page_obj': page_obj,
        'list_type': 'following',
        'following_count': following_count,
    }
    return render(request, 'My_app/community/follow_list.html', context)


# Followers List View
@login_required
def followers_list(request):
    """Show list of users who follow the current user"""
    # Get followers relationships
    followers = Follow.objects.filter(
        following=request.user
    ).select_related('follower__profile').order_by('-created_at')

    # Pagination
    paginator = Paginator(followers, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get count
    followers_count = followers.count()

    context = {
        'page_obj': page_obj,
        'list_type': 'followers',
        'followers_count': followers_count,
    }
    return render(request, 'My_app/community/follow_list.html', context)


# Toggle Follow View
@login_required
def toggle_follow(request, username):
    """Follow or unfollow a user"""
    target_user = get_object_or_404(User, username=username)

    # Can't follow yourself
    if target_user == request.user:
        messages.error(request, "You cannot follow yourself.")
        return redirect('user_profile', username=username)

    if request.method == 'POST':
        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            following=target_user
        )

        if not created:
            # Unfollow
            follow.delete()
            action = 'unfollowed'
            message_type = 'info'
            message_text = f'You unfollowed {target_user.username}'

            # Remove notification if exists
            Notification.objects.filter(
                user=target_user,
                notification_type='follow',
                actor=request.user
            ).delete()
        else:
            # Follow
            action = 'followed'
            message_type = 'success'
            message_text = f'You are now following {target_user.username}'

            # Create notification for the followed user
            Notification.objects.create(
                user=target_user,
                notification_type='follow',
                message=f'{request.user.username} started following you',
                actor=request.user
            )

        # For AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': action,
                'followers_count': target_user.followers.count(),
                'following_count': target_user.following.count(),
            })

        # For regular requests
        messages.add_message(request, messages.INFO if action == 'unfollowed' else messages.SUCCESS, message_text)
        return redirect('user_profile', username=username)

    # GET request - show confirmation
    is_following = Follow.objects.filter(
        follower=request.user,
        following=target_user
    ).exists()

    context = {
        'target_user': target_user,
        'is_following': is_following,
    }
    return render(request, 'My_app/community/confirm_follow.html', context)


# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q
import json
from .models import ChatMessage, ChatRoom, ChatRoomMember, Profile, SocialPost


@login_required
def messages_list(request):
    """Show list of conversations"""
    # Get conversations
    conversations = ChatMessage.get_conversations(request.user)

    context = {
        'conversations': conversations,
        'unread_messages_count': ChatMessage.get_unread_count(request.user),
    }
    return render(request, 'My_app/community/messages_list.html', context)


@login_required
def messages_conversation(request, username):
    """Show conversation with a specific user"""
    other_user = get_object_or_404(User, username=username)

    # Get or create chat room
    chat_room = ChatRoom.get_or_create_direct_chat(request.user, other_user)

    # Get messages
    messages = ChatMessage.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).order_by('created_at')

    # Mark messages as read
    messages.filter(receiver=request.user, is_read=False).update(is_read=True)

    context = {
        'other_user': other_user,
        'messages': messages,
        'chat_room': chat_room,
    }
    return render(request, 'My_app/community/messages_conversation.html', context)


@login_required
def api_send_message(request):
    """API endpoint to send a message"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_username = data.get('receiver')
            content = data.get('content')

            receiver = get_object_or_404(User, username=receiver_username)

            # Create message
            message = ChatMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content,
                message_type='text'
            )

            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'sender': message.sender.username,
                    'receiver': message.receiver.username,
                    'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_read': message.is_read
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def api_get_messages(request, username):
    """API endpoint to get messages with a user"""
    other_user = get_object_or_404(User, username=username)

    messages = ChatMessage.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).order_by('-created_at')[:50]  # Last 50 messages

    messages_list = []
    for msg in messages:
        messages_list.append({
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.username,
            'sender_avatar': msg.sender.profile.get_avatar_url(),
            'receiver': msg.receiver.username if msg.receiver else None,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': msg.is_read,
            'is_sender': msg.sender == request.user
        })

    return JsonResponse({'messages': messages_list})


@login_required
def user_profile(request, username):
    """View user profile"""
    profile_user = get_object_or_404(User, username=username)

    # Check if user can view profile
    if not profile_user.profile.can_view_profile(request.user):
        return render(request, 'My_app/community/profile_private.html', {'profile_user': profile_user})

    # Get user's posts
    posts = SocialPost.objects.filter(
        author=profile_user,
        is_active=True
    ).order_by('-created_at')[:20]

    # Check if current user is following this user
    is_following = False
    if request.user.is_authenticated:
        from .models import FollowRelationship
        is_following = FollowRelationship.objects.filter(
            follower=request.user,
            followed=profile_user
        ).exists()

    # Get recent activities
    recent_activities = SocialPost.objects.filter(
        author=profile_user
    ).order_by('-created_at')[:10]

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
        'recent_activities': recent_activities,
        'unread_messages_count': ChatMessage.get_unread_count(request.user),
    }

    return render(request, 'My_app/community/profile1.html', context)


@login_required
def search_users(request):
    """Search for users"""
    query = request.GET.get('q', '')
    users = []

    if query:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(profile__display_name__icontains=query)
        ).exclude(id=request.user.id)[:20]

    context = {
        'query': query,
        'users': users,
        'unread_messages_count': ChatMessage.get_unread_count(request.user),
    }

    return render(request, 'My_app/community/search.html', context)


@login_required
def api_follow_user(request):
    """API endpoint to follow/unfollow a user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')

            target_user = get_object_or_404(User, id=user_id)

            # Check if already following
            from .models import FollowRelationship
            follow_relationship, created = FollowRelationship.objects.get_or_create(
                follower=request.user,
                followed=target_user
            )

            if not created:
                # Already following, so unfollow
                follow_relationship.delete()
                action = 'unfollowed'
            else:
                action = 'followed'

            # Get updated counts
            followers_count = FollowRelationship.objects.filter(followed=target_user).count()

            return JsonResponse({
                'success': True,
                'action': action,
                'username': target_user.username,
                'followers_count': followers_count
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

# Add these at the bottom of your views.py (after all other views)


@login_required
def chat_list_view(request):
    """Display list of chat conversations"""
    # Get or create direct messages
    conversations = []

    # Get users you've messaged with or who have messaged you
    sent_messages = ChatMessage.objects.filter(sender=request.user).values('receiver').distinct()
    received_messages = ChatMessage.objects.filter(receiver=request.user).values('sender').distinct()

    user_ids = set()
    user_ids.update(msg['receiver'] for msg in sent_messages)
    user_ids.update(msg['sender'] for msg in received_messages)

    for user_id in user_ids:
        try:
            other_user = User.objects.get(id=user_id)
            last_message = ChatMessage.objects.filter(
                (Q(sender=request.user, receiver=other_user) |
                 Q(sender=other_user, receiver=request.user))
            ).order_by('-created_at').first()

            unread_count = ChatMessage.objects.filter(
                sender=other_user,
                receiver=request.user,
                is_read=False
            ).count()

            conversations.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count,
            })
        except User.DoesNotExist:
            continue

    # Sort by most recent message
    conversations.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else timezone.now(),
        reverse=True
    )

    # Get group chats
    group_chats = ChatRoom.objects.filter(
        members=request.user,
        is_group=True
    ).order_by('-updated_at')

    context = {
        'conversations': conversations,
        'group_chats': group_chats,
    }
    return render(request, 'My_app/community/chat_list.html', context)


@login_required
def chat_detail(request, username=None):
    """Display conversation with a specific user OR handle both"""
    if username:
        # This is a conversation with a specific user
        other_user = get_object_or_404(User, username=username)

        # Get messages
        messages = ChatMessage.objects.filter(
            (Q(sender=request.user, receiver=other_user) |
             Q(sender=other_user, receiver=request.user))
        ).order_by('created_at')

        # Mark messages as read
        messages.filter(receiver=request.user, is_read=False).update(is_read=True)

        context = {
            'other_user': other_user,
            'messages': messages,
        }
        return render(request, 'My_app/community/chat_detail.html', context)
    else:
        # No username provided, redirect to chat list
        return redirect('chat_list')


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import ChatMessage as Message, User, ChatRoom


@login_required
def api_chat_list(request):
    """Get list of chat conversations"""
    # Get all unique users you've chatted with
    sent_messages = Message.objects.filter(sender=request.user).values_list('receiver', flat=True).distinct()
    received_messages = Message.objects.filter(receiver=request.user).values_list('sender', flat=True).distinct()
    all_user_ids = set(list(sent_messages) + list(received_messages))

    chats = []
    for user_id in all_user_ids:
        try:
            user = User.objects.get(id=user_id)
            last_message = Message.objects.filter(
                Q(sender=request.user, receiver=user) | Q(sender=user, receiver=request.user)
            ).order_by('-timestamp').first()

            unread_count = Message.objects.filter(sender=user, receiver=request.user, is_read=False).count()

            chats.append({
                'id': user.id,
                'username': user.username,
                'name': user.profile.get_display_name(),
                'avatar': user.profile.get_avatar_url(),
                'last_message_preview': last_message.content[
                                            :50] + '...' if last_message and last_message.content else '',
                'last_message_time': last_message.timestamp if last_message else user.date_joined,
                'unread_count': unread_count
            })
        except User.DoesNotExist:
            continue

    # Sort by last message time
    chats.sort(key=lambda x: x['last_message_time'], reverse=True)

    return JsonResponse({'success': True, 'chats': chats})


@login_required
def api_get_messages(request, username):
    """Get messages between current user and another user"""
    try:
        other_user = User.objects.get(username=username)
        messages = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
        ).order_by('timestamp')

        # Mark messages as read
        Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)

        messages_list = []
        for msg in messages:
            messages_list.append({
                'sender': msg.sender.username,
                'content': msg.content,
                'timestamp': msg.timestamp,
                'read': msg.is_read,
                'file': msg.file.url if msg.file else None,
                'image': msg.image.url if msg.image else None,
                'file_name': msg.file_name,
                'file_size': msg.file_size,
                'file_type': msg.file_type
            })

        return JsonResponse({'success': True, 'messages': messages_list})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'})


@login_required
def api_send_message(request):
    """Send a message"""
    if request.method == 'POST':
        try:
            receiver_id = request.POST.get('receiver_id')
            content = request.POST.get('content', '')
            receiver = User.objects.get(id=receiver_id)

            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )

            # Handle file upload
            if 'file' in request.FILES:
                message.file = request.FILES['file']
                message.file_name = request.FILES['file'].name
                message.file_size = request.FILES['file'].size
                message.file_type = request.FILES['file'].content_type
                message.save()

            return JsonResponse({
                'success': True,
                'message': {
                    'sender': request.user.username,
                    'content': content,
                    'timestamp': message.timestamp,
                    'read': False
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


import json
import os
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Max, OuterRef, Subquery, Prefetch
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime, timedelta
import uuid
import hashlib

from My_app.models import (
    User, Profile, ChatRoom, ChatMessage, UserStatus,
    ChatRoomMember, Notification
)


# ==================== MESSAGE API ENDPOINTS ====================

@login_required
@require_GET
def get_messages(request, username):
    """Get messages between current user and another user with pagination"""
    try:
        other_user = get_object_or_404(User, username=username)

        # Get or create direct chat room
        chat_room = ChatRoom.get_or_create_direct_chat(request.user, other_user)

        # Get parameters
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit

        # Get messages
        messages = ChatMessage.objects.filter(
            chat_room=chat_room,
            deleted_for_everyone=False,
        ).filter(
            ~Q(deleted_by_sender=True, sender=request.user) |
            ~Q(deleted_by_receiver=True, receiver=request.user)
        ).select_related(
            'sender',
            'sender__profile',
            'receiver',
            'receiver__profile',
            'reply_to'
        ).order_by('-created_at')[offset:offset + limit]

        # Mark messages as read (only those sent by other user)
        unread_messages = messages.filter(
            sender=other_user,
            is_read=False
        )
        if unread_messages.exists():
            unread_messages.update(is_read=True, read_at=timezone.now())

            # Update chat room member unread count
            chat_member = ChatRoomMember.objects.filter(
                chat_room=chat_room,
                user=request.user
            ).first()
            if chat_member:
                chat_member.unread_count = max(0, chat_member.unread_count - unread_messages.count())
                chat_member.save()

        # Format response
        messages_list = []
        for msg in reversed(messages):  # Reverse to get chronological order
            messages_list.append(msg.to_dict())

        # Get total count for pagination
        total_messages = ChatMessage.objects.filter(
            chat_room=chat_room,
            deleted_for_everyone=False
        ).filter(
            ~Q(deleted_by_sender=True, sender=request.user) |
            ~Q(deleted_by_receiver=True, receiver=request.user)
        ).count()

        # Update user's last seen
        user_status, _ = UserStatus.objects.get_or_create(user=request.user)
        user_status.update_online_status(True)

        return JsonResponse({
            'success': True,
            'messages': messages_list,
            'total': total_messages,
            'page': page,
            'has_more': total_messages > (offset + limit),
            'room_id': str(chat_room.id) if chat_room else None
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def send_message(request):
    """Send a new message"""
    try:
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to = data.get('reply_to')

        if not receiver_id:
            return JsonResponse({
                'success': False,
                'error': 'Receiver ID is required'
            }, status=400)

        if not content and message_type == 'text':
            return JsonResponse({
                'success': False,
                'error': 'Message content is required'
            }, status=400)

        receiver = get_object_or_404(User, id=receiver_id)
        chat_room = ChatRoom.get_or_create_direct_chat(request.user, receiver)

        # Get replied message if reply_to is provided
        reply_to_message = None
        if reply_to:
            reply_to_message = ChatMessage.objects.filter(
                ws_message_id=reply_to,
                chat_room=chat_room
            ).first()

        # Create message
        message = ChatMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            chat_room=chat_room,
            content=content,
            message_type=message_type,
            reply_to=reply_to_message,
            is_delivered=True,
            delivered_at=timezone.now()
        )

        # Update chat room last message and activity
        chat_room.last_message = message
        chat_room.last_activity = message.created_at
        chat_room.message_count += 1
        chat_room.save()

        # Update receiver's unread count
        chat_member = ChatRoomMember.objects.filter(
            chat_room=chat_room,
            user=receiver
        ).first()
        if chat_member:
            chat_member.unread_count += 1
            chat_member.save()

        # Create notification for receiver
        Notification.objects.create(
            user=receiver,
            notification_type='message',
            title='New Message',
            message=f"New message from {request.user.profile.get_display_name()}",
            related_user=request.user
        )

        # Update sender's online status
        user_status, _ = UserStatus.objects.get_or_create(user=request.user)
        user_status.update_online_status(True)

        return JsonResponse({
            'success': True,
            'message': message.to_dict(),
            'room_id': str(chat_room.id)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@csrf_exempt
def upload_chat_file(request):
    """Upload file for chat message"""
    try:
        file = request.FILES.get('file')
        receiver_id = request.POST.get('receiver_id')
        message_type = request.POST.get('message_type', 'file')

        if not file:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=400)

        if not receiver_id:
            return JsonResponse({
                'success': False,
                'error': 'Receiver ID is required'
            }, status=400)

        receiver = get_object_or_404(User, id=receiver_id)
        chat_room = ChatRoom.get_or_create_direct_chat(request.user, receiver)

        # Validate file size (max 25MB)
        max_size = 25 * 1024 * 1024  # 25MB
        if file.size > max_size:
            return JsonResponse({
                'success': False,
                'error': f'File size exceeds {max_size // (1024 * 1024)}MB limit'
            }, status=400)

        # Validate file types
        allowed_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'],
            'file': [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain',
                'application/zip',
                'application/x-rar-compressed',
                'text/csv',
                'application/json',
                'application/x-python-code'
            ],
            'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/mp4'],
            'video': ['video/mp4', 'video/webm', 'video/ogg'],
            'chart': ['image/png', 'image/jpeg', 'image/svg+xml', 'text/csv', 'application/json']
        }

        if message_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'error': 'Invalid message type'
            }, status=400)

        if file.content_type not in allowed_types[message_type]:
            return JsonResponse({
                'success': False,
                'error': f'Invalid file type for {message_type}'
            }, status=400)

        # Generate unique filename
        file_ext = os.path.splitext(file.name)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"

        # Save file
        file_path = default_storage.save(f'chat_files/{unique_filename}', ContentFile(file.read()))

        # Create message
        message = ChatMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            chat_room=chat_room,
            content=f"Sent a {message_type} file",
            message_type=message_type,
            file=file_path,
            file_name=file.name,
            file_size=file.size,
            is_delivered=True,
            delivered_at=timezone.now()
        )

        # Update chat room
        chat_room.last_message = message
        chat_room.last_activity = message.created_at
        chat_room.message_count += 1
        chat_room.save()

        # Update receiver's unread count
        chat_member = ChatRoomMember.objects.filter(
            chat_room=chat_room,
            user=receiver
        ).first()
        if chat_member:
            chat_member.unread_count += 1
            chat_member.save()

        # Create notification
        Notification.objects.create(
            user=receiver,
            notification_type='message',
            title='New File',
            message=f"{request.user.profile.get_display_name()} sent you a file",
            related_user=request.user
        )

        return JsonResponse({
            'success': True,
            'message': message.to_dict(),
            'file_url': default_storage.url(file_path)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== USER STATUS API ====================

@login_required
@require_POST
def update_user_status(request):
    """Update user's online status"""
    try:
        data = json.loads(request.body)
        is_online = data.get('is_online', True)

        user_status, created = UserStatus.objects.get_or_create(user=request.user)
        user_status.update_online_status(is_online)

        return JsonResponse({
            'success': True,
            'is_online': user_status.is_online,
            'last_seen': user_status.last_seen.isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def get_user_status(request, username):
    """Get user's online status"""
    try:
        user = get_object_or_404(User, username=username)
        user_status = UserStatus.objects.filter(user=user).first()

        if user_status:
            # Check if user is actually online (seen within last 5 minutes)
            time_since_last_seen = timezone.now() - user_status.last_seen
            actually_online = user_status.is_online and time_since_last_seen.seconds < 300

            return JsonResponse({
                'success': True,
                'is_online': actually_online,
                'last_seen': user_status.last_seen.isoformat(),
                'is_typing': user_status.is_typing,
                'typing_to': user_status.typing_to.username if user_status.typing_to else None
            })

        return JsonResponse({
            'success': True,
            'is_online': False,
            'last_seen': None,
            'is_typing': False,
            'typing_to': None
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_typing_status(request):
    """Update user's typing status"""
    try:
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        is_typing = data.get('is_typing', False)

        user_status, _ = UserStatus.objects.get_or_create(user=request.user)

        if is_typing and receiver_id:
            receiver = get_object_or_404(User, id=receiver_id)
            chat_room = ChatRoom.get_or_create_direct_chat(request.user, receiver)
            user_status.update_typing_status(typing_to=receiver, typing_room=chat_room)
        else:
            user_status.clear_typing_status()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== CHAT LIST API ====================

@login_required
@require_GET
def get_chat_list(request):
    """Get list of chat conversations"""
    try:
        # Get all chat rooms where user is a member
        chat_rooms = ChatRoom.objects.filter(
            members=request.user,
            is_archived=False,
            is_active=True
        ).prefetch_related(
            Prefetch(
                'messages',
                queryset=ChatMessage.objects.filter(
                    deleted_for_everyone=False
                ).filter(
                    ~Q(deleted_by_sender=True, sender=request.user) |
                    ~Q(deleted_by_receiver=True, receiver=request.user)
                ).order_by('-created_at')
            ),
            'members',
            'members__profile'
        ).distinct()

        chats = []
        for room in chat_rooms:
            if room.room_type == 'direct' and room.member_count == 2:
                # Get the other user in direct chat
                other_user = room.members.exclude(id=request.user.id).first()
                if not other_user:
                    continue

                # Get user status
                user_status = UserStatus.objects.filter(user=other_user).first()

                # Get last message
                last_message = room.messages.first()

                # Get unread count
                chat_member = ChatRoomMember.objects.filter(
                    chat_room=room,
                    user=request.user
                ).first()
                unread_count = chat_member.unread_count if chat_member else 0

                # Format last message preview
                last_message_preview = "No messages yet"
                if last_message:
                    if last_message.message_type == 'image':
                        last_message_preview = "📷 Image"
                    elif last_message.message_type == 'file':
                        last_message_preview = "📎 File"
                    elif last_message.message_type == 'audio':
                        last_message_preview = "🎤 Voice message"
                    elif last_message.message_type == 'video':
                        last_message_preview = "🎥 Video"
                    else:
                        last_message_preview = last_message.content[:50] + (
                            '...' if len(last_message.content) > 50 else '')

                # Format last message time
                last_message_time = ""
                if last_message:
                    now = timezone.now()
                    message_time = last_message.created_at

                    if message_time.date() == now.date():
                        last_message_time = message_time.strftime('%H:%M')
                    elif message_time.date() == now.date() - timedelta(days=1):
                        last_message_time = 'Yesterday'
                    elif (now - message_time).days < 7:
                        last_message_time = message_time.strftime('%A')
                    else:
                        last_message_time = message_time.strftime('%d/%m/%y')

                chats.append({
                    'user_id': other_user.id,
                    'username': other_user.username,
                    'display_name': other_user.profile.get_display_name(),
                    'avatar': other_user.profile.get_avatar_url(),
                    'is_online': user_status.is_online if user_status else False,
                    'last_seen': user_status.last_seen.isoformat() if user_status else None,
                    'last_message_preview': last_message_preview,
                    'last_message_time': last_message_time,
                    'last_message_timestamp': last_message.created_at.isoformat() if last_message else None,
                    'unread_count': unread_count,
                    'room_id': str(room.id),
                    'is_kyc_verified': other_user.profile.kyc_verified,
                    'plan': other_user.profile.plan,
                })

        # Sort by last message timestamp (most recent first)
        chats.sort(key=lambda x: x.get('last_message_timestamp') or '', reverse=True)

        return JsonResponse({
            'success': True,
            'chats': chats,
            'total': len(chats)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== MESSAGE ACTIONS API ====================

@login_required
@require_POST
def mark_messages_as_read(request):
    """Mark messages as read"""
    try:
        data = json.loads(request.body)
        message_ids = data.get('message_ids', [])
        room_id = data.get('room_id')

        if room_id:
            # Mark all messages in room as read
            chat_room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
            messages = ChatMessage.objects.filter(
                chat_room=chat_room,
                receiver=request.user,
                is_read=False
            )

            updated_count = 0
            for message in messages:
                if message.mark_as_read():
                    updated_count += 1

            # Reset unread count in chat room member
            chat_member = ChatRoomMember.objects.filter(
                chat_room=chat_room,
                user=request.user
            ).first()
            if chat_member:
                chat_member.unread_count = 0
                chat_member.last_read = timezone.now()
                chat_member.save()

            return JsonResponse({
                'success': True,
                'updated_count': updated_count
            })

        elif message_ids:
            # Mark specific messages as read
            messages = ChatMessage.objects.filter(
                id__in=message_ids,
                receiver=request.user
            )

            updated_count = 0
            for message in messages:
                if message.mark_as_read():
                    updated_count += 1

            return JsonResponse({
                'success': True,
                'updated_count': updated_count
            })

        return JsonResponse({
            'success': False,
            'error': 'Either room_id or message_ids is required'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def delete_message(request):
    """Delete a message"""
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        delete_for_everyone = data.get('delete_for_everyone', False)

        if not message_id:
            return JsonResponse({
                'success': False,
                'error': 'Message ID is required'
            })

        message = get_object_or_404(ChatMessage, id=message_id)

        # Check permissions
        if message.sender != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You can only delete your own messages'
            }, status=403)

        if delete_for_everyone:
            message.deleted_for_everyone = True
            message.content = "This message was deleted"
            if message.file:
                message.file.delete(save=False)
                message.file = None
        else:
            message.deleted_by_sender = True

        message.save()

        return JsonResponse({
            'success': True,
            'message': 'Message deleted successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def react_to_message(request):
    """Add reaction to a message"""
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        emoji = data.get('emoji')

        if not message_id or not emoji:
            return JsonResponse({
                'success': False,
                'error': 'Message ID and emoji are required'
            })

        message = get_object_or_404(ChatMessage, id=message_id)

        # Check if user can see this message
        if message.receiver != request.user and message.sender != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You cannot react to this message'
            }, status=403)

        message.add_reaction(request.user, emoji)

        return JsonResponse({
            'success': True,
            'reactions': message.reactions
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== CHAT ROOM MANAGEMENT ====================

@login_required
@require_POST
def create_chat_room(request):
    """Create a new group chat room"""
    try:
        data = json.loads(request.body)
        name = data.get('name')
        user_ids = data.get('user_ids', [])
        is_public = data.get('is_public', False)

        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Room name is required'
            })

        if not user_ids:
            return JsonResponse({
                'success': False,
                'error': 'At least one other user is required'
            })

        # Create room
        room = ChatRoom.objects.create(
            name=name,
            room_type='group',
            is_public=is_public,
            creator=request.user
        )

        # Add creator as admin
        ChatRoomMember.objects.create(
            chat_room=room,
            user=request.user,
            role='owner'
        )

        # Add other users
        for user_id in user_ids:
            user = get_object_or_404(User, id=user_id)
            ChatRoomMember.objects.create(
                chat_room=room,
                user=user,
                role='member'
            )

        # Update member count
        room.member_count = len(user_ids) + 1
        room.save()

        return JsonResponse({
            'success': True,
            'room': {
                'id': str(room.id),
                'name': room.name,
                'room_type': room.room_type,
                'member_count': room.member_count,
                'creator': request.user.username
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import SocialPost, SocialComment, SocialPostLike, FollowRelationship


def social_post_detail(request, pk):
    """View a single social post in detail"""
    post = get_object_or_404(SocialPost, pk=pk, is_active=True)

    # Check if user can view this post
    if not post.can_view(request.user):
        return render(request, 'posts/access_denied.html', {'post': post})

    # Increment view count
    post.increment_views()

    # Get comments
    comments = SocialComment.objects.filter(
        post=post,
        is_active=True,
        parent_comment=None
    ).select_related('author', 'author__profile').order_by('-created_at')

    # Check if user liked this post
    is_liked = False
    if request.user.is_authenticated:
        is_liked = SocialPostLike.objects.filter(
            post=post,
            user=request.user,
            is_active=True
        ).exists()

    # Check if user is following the author
    is_following = False
    if request.user.is_authenticated and request.user != post.author:
        is_following = FollowRelationship.objects.filter(
            follower=request.user,
            followed=post.author
        ).exists()

    context = {
        'post': post,
        'comments': comments,
        'is_liked': is_liked,
        'is_following': is_following,
        'comment_count': post.comments_count,
        'like_count': post.likes_count,
    }

    return render(request, 'posts/post_detail.html', context)


def posts_by_tag(request, tag):
    """View posts by tag"""
    posts = SocialPost.objects.filter(
        tags__contains=[tag],
        is_active=True,
        visibility='public'
    ).select_related('author', 'author__profile').order_by('-created_at')

    context = {
        'tag': tag,
        'posts': posts,
    }

    return render(request, 'posts/posts_by_tag.html', context)


# community/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, F, Value, Case, When, IntegerField
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.models import User
from .models import Profile, SocialPost, FollowRelationship, UserStatus, Notification, ChatRoom
from datetime import timedelta
from django.utils import timezone


@login_required
def advanced_search(request):
    """Advanced search with filters"""
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)

    # Get filter parameters
    user_type = request.GET.get('type', '')
    experience = request.GET.get('experience', '')
    market = request.GET.get('market', '')
    location = request.GET.get('location', '')
    sort_by = request.GET.get('sort', 'relevance')
    quick_filter = request.GET.get('quick_filter', 'all')

    # Start with all users (excluding self)
    users = User.objects.exclude(id=request.user.id).select_related(
        'profile', 'user_status'
    ).prefetch_related(
        'followers', 'following'
    )

    # Apply quick filters
    if quick_filter == 'online':
        users = users.filter(user_status__is_online=True)
    elif quick_filter == 'verified':
        users = users.filter(profile__kyc_verified=True)
    elif quick_filter == 'mentors':
        users = users.filter(profile__plan__in=['Premium', 'Enterprise'])
    elif quick_filter == 'institutional':
        users = users.filter(profile__plan='Enterprise')
    elif quick_filter == 'top_traders':
        users = users.filter(profile__reputation_score__gte=1000)

    # Apply search query
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(profile__display_name__icontains=query) |
            Q(profile__bio__icontains=query) |
            Q(profile__trading_style__icontains=query) |
            Q(profile__community_username__icontains=query)
        )

    # Apply advanced filters
    if user_type:
        if user_type == 'trader':
            users = users.filter(profile__trading_style__isnull=False)
        elif user_type == 'analyst':
            users = users.filter(profile__bio__icontains='analyst')
        elif user_type == 'mentor':
            users = users.filter(profile__plan__in=['Premium', 'Enterprise'])
        elif user_type == 'institutional':
            users = users.filter(profile__plan='Enterprise')

    if experience:
        users = users.filter(profile__plan=experience.capitalize())

    if market:
        users = users.filter(profile__favorite_symbols__contains=[market])

    if location:
        users = users.filter(profile__country__icontains=location)

    # Apply sorting
    if sort_by == 'followers':
        users = users.order_by('-profile__followers_count')
    elif sort_by == 'recent':
        users = users.order_by('-user_status__last_seen')
    elif sort_by == 'performance':
        users = users.order_by('-profile__reputation_score')
    elif sort_by == 'joined':
        users = users.order_by('-date_joined')
    else:  # relevance
        # For relevance, prioritize exact matches and high reputation
        users = users.annotate(
            relevance_score=Case(
                When(username__iexact=query, then=Value(100)),
                When(profile__display_name__iexact=query, then=Value(80)),
                When(profile__trading_style__iexact=query, then=Value(60)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-relevance_score', '-profile__reputation_score')

    # Get trending traders (most followers in last 7 days)
    week_ago = timezone.now() - timedelta(days=7)

    trending_traders = User.objects.exclude(id=request.user.id).filter(
        profile__followers_count__gt=0
    ).select_related('profile').order_by('-profile__followers_count')[:10]

    # Get recently active users
    recently_active = User.objects.exclude(id=request.user.id).filter(
        user_status__last_seen__gte=timezone.now() - timedelta(hours=24)
    ).select_related('profile', 'user_status').order_by('-user_status__last_seen')[:10]

    # Pagination
    paginator = Paginator(users, 20)  # 20 users per page
    try:
        users_page = paginator.page(page)
    except:
        users_page = paginator.page(1)

    context = {
        'query': query,
        'users': users_page,
        'trending_traders': trending_traders,
        'recently_active': recently_active,
        'page_obj': users_page,
        'total_users': users.count(),
        'filter_params': {
            'type': user_type,
            'experience': experience,
            'market': market,
            'location': location,
            'sort': sort_by,
            'quick_filter': quick_filter,
        }
    }

    return render(request, 'My_app/community/search.html', context)


@csrf_exempt
@require_POST
def api_follow_user(request):
    """API endpoint to follow/unfollow user"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')

        if not user_id:
            return JsonResponse({'error': 'User ID required'}, status=400)

        user_to_follow = get_object_or_404(User, id=user_id)

        if user_to_follow == request.user:
            return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

        # Check if already following
        is_following = FollowRelationship.objects.filter(
            follower=request.user,
            followed=user_to_follow
        ).exists()

        if is_following:
            # Unfollow
            FollowRelationship.objects.filter(
                follower=request.user,
                followed=user_to_follow
            ).delete()
            is_following = False
        else:
            # Follow
            FollowRelationship.objects.create(
                follower=request.user,
                followed=user_to_follow
            )
            is_following = True

            # Create notification
            Notification.objects.create(
                user=user_to_follow,
                notification_type='new_follower',
                title='New Follower',
                message=f'{request.user.profile.get_display_name()} started following you',
                related_user=request.user
            )

        # Get updated follower count
        followers_count = user_to_follow.followers.count()

        return JsonResponse({
            'success': True,
            'is_following': is_following,
            'followers_count': followers_count
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_search_suggestions(request):
    """API for real-time search suggestions"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(profile__display_name__icontains=query)
    ).exclude(id=request.user.id).select_related('profile')[:10]

    suggestions = []
    for user in users:
        suggestions.append({
            'id': user.id,
            'username': user.username,
            'display_name': user.profile.get_display_name(),
            'avatar': user.profile.get_avatar_url(),
            'type': 'user',
            'bio_preview': (user.profile.bio[:50] + '...') if user.profile.bio and len(user.profile.bio) > 50 else (
                        user.profile.bio or ''),
            'followers': user.profile.followers_count,
            'is_verified': user.profile.kyc_verified
        })

    return JsonResponse({'suggestions': suggestions})

@csrf_exempt
@require_POST
@login_required
def api_message_user(request, username):
    """API to start messaging a user"""
    user_to_message = get_object_or_404(User, username=username)

    # Get or create direct chat room
    chat_room = ChatRoom.get_or_create_direct_chat(request.user, user_to_message)

    # Return redirect to chat with username (not room ID)
    return JsonResponse({
        'success': True,
        'chat_room_id': chat_room.id,
        'redirect_url': f'/community/messages/{user_to_message.username}/'  # Use username
    })


# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


@csrf_exempt
@require_POST
@login_required
def api_update_bio(request):
    """API endpoint to update user bio"""
    try:
        data = json.loads(request.body)
        bio = data.get('bio', '').strip()

        # Update profile bio
        request.user.profile.bio = bio
        request.user.profile.save()

        return JsonResponse({
            'success': True,
            'bio': bio
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
@require_POST
@login_required
def api_update_profile_settings(request):
    """API endpoint to update profile settings"""
    try:
        data = json.loads(request.body)
        profile = request.user.profile

        # Update display name
        if 'display_name' in data:
            profile.display_name = data['display_name']

        # Update trading style
        if 'trading_style' in data:
            profile.trading_style = data['trading_style']

        # Update settings
        if 'show_online_status' in data:
            profile.show_online_status = data['show_online_status']

        if 'show_trading_stats' in data:
            profile.show_trading_stats = data['show_trading_stats']

        if 'email_notifications' in data:
            profile.email_notifications = data['email_notifications']

        if 'push_notifications' in data:
            profile.push_notifications = data['push_notifications']

        profile.save()

        return JsonResponse({
            'success': True,
            'message': 'Profile settings updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)