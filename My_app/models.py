# models.py - COMPLETE UPDATED FILE
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import datetime
from django.urls import reverse
from django.db.models import Sum
from django.core.exceptions import ValidationError


class Profile(models.Model):
    """Enhanced Profile model with community features"""
    PLAN_CHOICES = [
        ('Starter', 'Starter - Basic features'),
        ('Pro', 'Pro - Advanced features'),
        ('Premium', 'Premium - All features + priority support'),
        ('Enterprise', 'Enterprise - Custom solutions'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)

    # subscription plan with choices
    plan = models.CharField(
        max_length=50,
        choices=PLAN_CHOICES,
        default="Starter"
    )

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        default='profile_pictures/default.png',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # KYC Status
    kyc_verified = models.BooleanField(default=False)
    kyc_submitted_at = models.DateTimeField(blank=True, null=True)
    kyc_verified_at = models.DateTimeField(blank=True, null=True)

    # Community Features
    community_username = models.CharField(max_length=50, blank=True, null=True, unique=True)
    display_name = models.CharField(max_length=100, blank=True, null=True)
    is_private = models.BooleanField(default=False)
    show_trading_stats = models.BooleanField(default=True)
    show_online_status = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)

    # Trading Preferences
    trading_style = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('day_trader', 'Day Trader'),
            ('swing_trader', 'Swing Trader'),
            ('position_trader', 'Position Trader'),
            ('scalper', 'Scalper'),
            ('investor', 'Investor'),
        ]
    )
    favorite_symbols = models.JSONField(default=list, blank=True)

    # Stats (cached for performance)
    total_posts = models.PositiveIntegerField(default=0)
    total_likes_received = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)
    reputation_score = models.PositiveIntegerField(default=0)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.user.username

    def get_plan_display_class(self):
        """Return Bootstrap class for plan badge"""
        plan_classes = {
            'Starter': 'bg-secondary',
            'Pro': 'bg-info',
            'Premium': 'bg-warning',
            'Enterprise': 'bg-danger',
        }
        return plan_classes.get(self.plan, 'bg-secondary')

    @property
    def wallet_balance(self):
        try:
            return self.user.wallet.balance
        except:
            wallet, created = Wallet.objects.get_or_create(user=self.user)
            return wallet.balance

    def get_transactions(self, limit=10):
        return self.user.transactions.all().order_by('-created_at')[:limit]

    def get_kyc_status_display(self):
        """Get KYC status for display"""
        try:
            kyc = self.user.kyc_application
            return kyc.get_status_display()
        except:
            return "Not Submitted"

    def can_make_transaction(self):
        """Check if user can make transactions (KYC verified)"""
        if self.plan in ['Premium', 'Enterprise']:
            return True
        return self.kyc_verified

    # Community Methods
    def get_avatar_url(self):
        """Get avatar URL for community posts"""
        if self.avatar:
            return self.avatar.url
        elif self.profile_picture:
            return self.profile_picture.url
        return '/static/images/default-avatar.png'

    def get_display_name(self):
        """Get display name for community"""
        return self.display_name or self.user.get_full_name() or self.user.username

    def update_community_stats(self):
        """Update cached community stats"""
        from .models import SocialPost, SocialPostLike, SocialComment, FollowRelationship

        self.total_posts = SocialPost.objects.filter(author=self.user).count()
        self.total_likes_received = SocialPostLike.objects.filter(
            post__author=self.user,
            is_active=True
        ).count()
        self.total_comments = SocialComment.objects.filter(author=self.user, is_active=True).count()
        self.followers_count = FollowRelationship.objects.filter(followed=self.user).count()
        self.following_count = FollowRelationship.objects.filter(follower=self.user).count()

        # Calculate reputation score
        self.reputation_score = (
                self.total_posts * 10 +
                self.total_likes_received * 2 +
                self.total_comments * 5 +
                self.followers_count * 3
        )
        self.save(update_fields=[
            'total_posts', 'total_likes_received', 'total_comments',
            'followers_count', 'following_count', 'reputation_score'
        ])

    def is_following(self, user):
        """Check if this user is following another user"""
        from .models import FollowRelationship
        return FollowRelationship.objects.filter(
            follower=self.user,
            followed=user
        ).exists()

    def can_view_profile(self, requesting_user):
        """Check if requesting user can view this profile"""
        if not self.is_private:
            return True
        if requesting_user == self.user:
            return True
        if self.is_following(requesting_user):
            return True
        return requesting_user.is_staff

    def get_recent_activity(self, limit=5):
        """Get user's recent community activity"""
        from .models import SocialPost, SocialComment
        posts = SocialPost.objects.filter(author=self.user).order_by('-created_at')[:limit]
        comments = SocialComment.objects.filter(author=self.user).order_by('-created_at')[:limit]
        return {
            'posts': posts,
            'comments': comments
        }


class KYCApplication(models.Model):
    """Fixed KYCApplication model"""
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUBMITTED", "Submitted - Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("NEEDS_REVISION", "Needs Revision"),
    ]

    DOCUMENT_TYPES = [
        ("PASSPORT", "Passport"),
        ("NATIONAL_ID", "National ID Card"),
        ("DRIVERS_LICENSE", "Driver's License"),
        ("RESIDENCE_PERMIT", "Residence Permit"),
        ("VOTERS_ID", "Voter's ID"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc_application")

    # Personal Information
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(default=datetime.date(2000, 1, 1))
    nationality = models.CharField(max_length=100)

    # Address Information
    address = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')

    # Document Information
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=100)
    document_issue_date = models.DateField(default=datetime.date(2020, 1, 1))
    document_expiry_date = models.DateField(default=datetime.date(2030, 1, 1))

    # Document Images
    document_front = models.ImageField(upload_to='kyc_docs/', blank=True, null=True)
    document_back = models.ImageField(upload_to='kyc_docs/', blank=True, null=True)
    selfie_with_document = models.ImageField(upload_to='kyc_selfies/', blank=True, null=True)
    proof_of_address = models.FileField(upload_to="kyc/address_proof/", blank=True, null=True)

    # Status and Admin
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="kyc_reviews")

    # Notes and Reasons
    admin_notes = models.TextField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    revision_notes = models.TextField(blank=True, null=True)

    # Verification Score (0-100)
    verification_score = models.IntegerField(default=0)
    automated_check_passed = models.BooleanField(default=False)

    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "KYC Application"
        verbose_name_plural = "KYC Applications"
        ordering = ['-submitted_at']

    def __str__(self):
        return f"KYC-{self.user.username}-{self.status}"

    def save(self, *args, **kwargs):
        # Update user profile when KYC is approved
        if self.pk:
            try:
                old_instance = KYCApplication.objects.get(pk=self.pk)
                if old_instance.status != "APPROVED" and self.status == "APPROVED":
                    # Update profile KYC status
                    profile = self.user.profile
                    profile.kyc_verified = True
                    profile.kyc_verified_at = timezone.now()

                    # Update user's country if empty
                    if not profile.country:
                        profile.country = self.country

                    profile.save()
                    self.reviewed_at = timezone.now()
            except KYCApplication.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    @property
    def is_verified(self):
        return self.status == "APPROVED"

    @property
    def is_pending_review(self):
        return self.status in ["SUBMITTED", "NEEDS_REVISION"]

    @property
    def verification_progress(self):
        """Calculate completion percentage of KYC"""
        required_fields = [
            self.full_name, self.date_of_birth, self.nationality,
            self.address, self.city, self.country, self.postal_code,
            self.document_type, self.document_number, self.document_front,
            self.selfie_with_document
        ]
        completed = sum(1 for field in required_fields if field)
        return int((completed / len(required_fields)) * 100)

    @property
    def days_since_submission(self):
        """Days since KYC was submitted"""
        if self.submitted_at:
            return (timezone.now() - self.submitted_at).days
        return 0

    def approve(self, admin_user, notes=""):
        """Approve KYC application"""
        self.status = "APPROVED"
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.save()

    def reject(self, admin_user, reason):
        """Reject KYC application"""
        self.status = "REJECTED"
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def request_revision(self, admin_user, notes):
        """Request revision from user"""
        self.status = "NEEDS_REVISION"
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.revision_notes = notes
        self.save()


class Wallet(models.Model):
    """Enhanced Wallet model"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For multi-currency support
    balances = models.JSONField(default=dict, blank=True)

    # Transaction limits
    daily_deposit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=5000.00)
    daily_withdrawal_limit = models.DecimalField(max_digits=15, decimal_places=2, default=2000.00)
    daily_transfer_limit = models.DecimalField(max_digits=15, decimal_places=2, default=1000.00)

    # Tracking
    total_deposited = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_withdrawn = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_transferred = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Community Trading Stats
    total_trades = models.PositiveIntegerField(default=0)
    winning_trades = models.PositiveIntegerField(default=0)
    losing_trades = models.PositiveIntegerField(default=0)
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"

    def __str__(self):
        return f"{self.user.username}'s Wallet - {self.balance} {self.currency}"

    def get_available_balance(self):
        """Get available balance considering pending withdrawals"""
        pending_withdrawals = Transaction.objects.filter(
            user=self.user,
            txn_type="WITHDRAW",
            status__in=["PENDING", "PROCESSING"]
        ).aggregate(total=Sum('amount'))['total'] or 0

        return self.balance - Decimal(str(pending_withdrawals))

    def deposit(self, amount, currency="USD", reference="", description=""):
        """Deposit money into wallet"""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        # Check KYC for large deposits
        profile = self.user.profile
        if amount > 1000 and not profile.kyc_verified:
            raise ValueError("KYC verification required for deposits over $1000")

        # Get balance change record
        old_balance = self.balance
        new_balance = old_balance + Decimal(str(amount))

        # Update wallet balance
        self.balance = new_balance
        self.total_deposited += Decimal(str(amount))
        self.save()

        # Create transaction
        txn = Transaction.objects.create(
            user=self.user,
            transaction_id=uuid.uuid4(),
            txn_type="DEPOSIT",
            amount=amount,
            currency=currency,
            status="COMPLETED",
            payment_method="WALLET",
            description=description or f"Wallet deposit: {reference}",
            balance_before=old_balance,
            balance_after=new_balance,
            metadata={
                'reference': reference,
                'action': 'deposit',
                'currency': currency
            }
        )

        # Create balance change record
        BalanceChange.objects.create(
            user=self.user,
            old_balance=old_balance,
            new_balance=new_balance,
            change=amount,
            transaction_type="DEPOSIT",
            description=description or f"Deposit: {reference}",
            reference=reference,
            transaction=txn
        )

        return txn

    def withdraw(self, amount, currency="USD", reference="", description=""):
        """Withdraw money from wallet"""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        # Check available balance
        available_balance = self.get_available_balance()
        if available_balance < amount:
            raise ValueError(f"Insufficient balance. Available: {available_balance}")

        # Check KYC for withdrawals
        profile = self.user.profile
        if amount > 500 and not profile.kyc_verified:
            raise ValueError("KYC verification required for withdrawals over $500")

        # Get balance change record
        old_balance = self.balance
        new_balance = old_balance - Decimal(str(amount))

        # Update wallet balance
        self.balance = new_balance
        self.total_withdrawn += Decimal(str(amount))
        self.save()

        # Create transaction
        txn = Transaction.objects.create(
            user=self.user,
            transaction_id=uuid.uuid4(),
            txn_type="WITHDRAW",
            amount=amount,
            currency=currency,
            status="PENDING",
            payment_method="WALLET",
            description=description or f"Wallet withdrawal: {reference}",
            balance_before=old_balance,
            balance_after=new_balance,
            metadata={
                'reference': reference,
                'action': 'withdrawal',
                'currency': currency
            }
        )

        # Create balance change record
        BalanceChange.objects.create(
            user=self.user,
            old_balance=old_balance,
            new_balance=new_balance,
            change=-amount,
            transaction_type="WITHDRAW",
            description=description or f"Withdrawal: {reference}",
            reference=reference,
            transaction=txn
        )

        return txn

    def transfer(self, to_user, amount, currency="USD", description=""):
        """Transfer money to another user"""
        # Check KYC for transfers
        profile = self.user.profile
        if amount > 500 and not profile.kyc_verified:
            raise ValueError("KYC verification required for transfers over $500")

        try:
            to_wallet = Wallet.objects.get(user=to_user)
        except Wallet.DoesNotExist:
            raise ValueError("Recipient wallet not found")

        if self.balance < amount:
            raise ValueError("Insufficient balance")

        # Create sender transaction
        txn_sender = Transaction.objects.create(
            user=self.user,
            transaction_id=uuid.uuid4(),
            txn_type="TRANSFER",
            amount=amount,
            currency=currency,
            status="PENDING",
            description=f"Transfer to {to_user.username}: {description}",
            to_user=to_user
        )

        # Create receiver transaction
        txn_receiver = Transaction.objects.create(
            user=to_user,
            transaction_id=uuid.uuid4(),
            txn_type="TRANSFER",
            amount=amount,
            currency=currency,
            status="PENDING",
            description=f"Transfer from {self.user.username}: {description}",
            from_user=self.user
        )

        # Perform transfer
        old_balance_sender = self.balance
        new_balance_sender = old_balance_sender - Decimal(str(amount))

        old_balance_receiver = to_wallet.balance
        new_balance_receiver = old_balance_receiver + Decimal(str(amount))

        # Update sender wallet
        self.balance = new_balance_sender
        self.total_transferred += Decimal(str(amount))
        self.save()

        # Update receiver wallet
        to_wallet.balance = new_balance_receiver
        to_wallet.total_deposited += Decimal(str(amount))
        to_wallet.save()

        # Update transactions
        txn_sender.balance_before = old_balance_sender
        txn_sender.balance_after = new_balance_sender
        txn_sender.status = "COMPLETED"
        txn_sender.save()

        txn_receiver.balance_before = old_balance_receiver
        txn_receiver.balance_after = new_balance_receiver
        txn_receiver.status = "COMPLETED"
        txn_receiver.save()

        # Create balance changes
        BalanceChange.objects.create(
            user=self.user,
            old_balance=old_balance_sender,
            new_balance=new_balance_sender,
            change=-amount,
            transaction_type="TRANSFER",
            description=f"Transfer to {to_user.username}: {description}",
            reference=txn_sender.reference,
            transaction=txn_sender
        )

        BalanceChange.objects.create(
            user=to_user,
            old_balance=old_balance_receiver,
            new_balance=new_balance_receiver,
            change=amount,
            transaction_type="TRANSFER",
            description=f"Transfer from {self.user.username}: {description}",
            reference=txn_receiver.reference,
            transaction=txn_receiver
        )

        return txn_sender, txn_receiver

    def update_trading_stats(self, profit=None, loss=None, is_winning_trade=False):
        """Update trading statistics"""
        if profit is not None:
            self.total_profit += Decimal(str(profit))
        if loss is not None:
            self.total_loss += Decimal(str(loss))

        self.total_trades += 1
        if is_winning_trade:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        self.save()

    def get_win_rate(self):
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0
        return (self.winning_trades / self.total_trades) * 100

    def get_net_profit_loss(self):
        """Calculate net profit/loss"""
        return self.total_profit - self.total_loss

    def get_balance_history(self, limit=10):
        """Get recent balance changes"""
        return BalanceChange.objects.filter(user=self.user).order_by('-timestamp')[:limit]

    def get_daily_stats(self):
        """Get today's transaction statistics"""
        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))

        today_deposits = Transaction.objects.filter(
            user=self.user,
            txn_type="DEPOSIT",
            created_at__gte=today_start,
            status="COMPLETED"
        ).aggregate(total=Sum('amount'))['total'] or 0

        today_withdrawals = Transaction.objects.filter(
            user=self.user,
            txn_type="WITHDRAW",
            created_at__gte=today_start,
            status="COMPLETED"
        ).aggregate(total=Sum('amount'))['total'] or 0

        today_transfers = Transaction.objects.filter(
            user=self.user,
            txn_type="TRANSFER",
            created_at__gte=today_start,
            status="COMPLETED"
        ).aggregate(total=Sum('amount'))['total'] or 0

        return {
            'deposits': today_deposits,
            'withdrawals': today_withdrawals,
            'transfers': today_transfers
        }

    @classmethod
    def get_or_create_wallet(cls, user):
        """Get or create wallet for user"""
        wallet, created = cls.objects.get_or_create(user=user)
        return wallet


class BalanceChange(models.Model):
    """Model to track all balance changes"""
    TRANSACTION_TYPES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('BONUS', 'Bonus'),
        ('ADMIN_MOD', 'Admin Modification'),
        ('REFUND', 'Refund'),
        ('FEE', 'Fee'),
        ('TRANSFER', 'Transfer'),
        ('INTEREST', 'Interest'),
        ('TRADE_PROFIT', 'Trade Profit'),
        ('TRADE_LOSS', 'Trade Loss'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_changes')
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='admin_modifications')
    old_balance = models.DecimalField(max_digits=15, decimal_places=2)
    new_balance = models.DecimalField(max_digits=15, decimal_places=2)
    change = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    transaction = models.ForeignKey('Transaction', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='balance_changes')
    timestamp = models.DateTimeField(auto_now_add=True)

    # For trade-related changes
    trade_post = models.ForeignKey('SocialPost', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='balance_changes')
    trading_symbol = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Balance Change"
        verbose_name_plural = "Balance Changes"

    def __str__(self):
        change_symbol = '+' if self.change > 0 else ''
        return f"{self.user.username}: {change_symbol}{self.change} ({self.old_balance}→{self.new_balance})"

    @classmethod
    def create_from_transaction(cls, transaction):
        """Create balance change record from transaction"""
        if transaction.balance_before is not None and transaction.balance_after is not None:
            return cls.objects.create(
                user=transaction.user,
                old_balance=transaction.balance_before,
                new_balance=transaction.balance_after,
                change=transaction.balance_after - transaction.balance_before,
                transaction_type=transaction.txn_type,
                description=transaction.description or f"{transaction.txn_type} transaction",
                reference=transaction.reference,
                transaction=transaction
            )
        return None


class Transaction(models.Model):
    """Enhanced Transaction model"""
    TXN_TYPES = [
        ("DEPOSIT", "Deposit"),
        ("WITHDRAW", "Withdraw"),
        ("TRANSFER", "Transfer"),
        ("FEE", "Fee"),
        ("BONUS", "Bonus"),
        ("REFUND", "Refund"),
        ("INTEREST", "Interest"),
        ("CHARGEBACK", "Chargeback"),
        ("REVERSAL", "Reversal"),
        ("ADMIN_MOD", "Admin Modification"),
        ("TRADE_PROFIT", "Trade Profit"),
        ("TRADE_LOSS", "Trade Loss"),
    ]

    TXN_STATUS = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
        ("ON_HOLD", "On Hold"),
        ("REFUNDED", "Refunded"),
        ("PARTIAL", "Partially Completed"),
        ("EXPIRED", "Expired"),
    ]

    PAYMENT_METHODS = [
        ("MPESA", "M-Pesa"),
        ("PAYPAL", "PayPal"),
        ("ALIPAY", "Alipay"),
        ("MASTERCARD", "MasterCard"),
        ("VISA", "Visa"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CREDIT_CARD", "Credit Card"),
        ("DEBIT_CARD", "Debit Card"),
        ("STRIPE", "Stripe"),
        ("CRYPTO", "Cryptocurrency"),
        ("WALLET", "Wallet Balance"),
        ("APPLE_PAY", "Apple Pay"),
        ("GOOGLE_PAY", "Google Pay"),
        ("SKRILL", "Skrill"),
        ("NETELLER", "Neteller"),
        ("ADMIN", "Admin"),
    ]

    CURRENCY_CHOICES = [
        ("USD", "US Dollar"),
        ("EUR", "Euro"),
        ("GBP", "British Pound"),
        ("KES", "Kenyan Shilling"),
        ("CNY", "Chinese Yuan"),
        ("JPY", "Japanese Yen"),
        ("AUD", "Australian Dollar"),
        ("CAD", "Canadian Dollar"),
        ("INR", "Indian Rupee"),
        ("ZAR", "South African Rand"),
    ]

    # Core payment gateway integration fields
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True
    )

    gateway_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Gateway Transaction ID"
    )

    payment_gateway = models.CharField(
        max_length=50,
        choices=[
            ("MPESA", "M-Pesa"),
            ("PAYPAL", "PayPal"),
            ("ALIPAY", "Alipay"),
            ("STRIPE", "Stripe"),
            ("RAZORPAY", "Razorpay"),
            ("FLUTTERWAVE", "Flutterwave"),
            ("PAYSTACK", "Paystack"),
            ("SQUARE", "Square"),
            ("CHECKOUT", "Checkout.com"),
            ("ADYEN", "Adyen"),
            ("NONE", "None"),
        ],
        default="NONE"
    )

    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Gateway Raw Response"
    )

    gateway_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("CREATED", "Created"),
            ("AUTHORIZED", "Authorized"),
            ("CAPTURED", "Captured"),
            ("SETTLED", "Settled"),
            ("DECLINED", "Declined"),
            ("VOIDED", "Voided"),
            ("REFUNDED", "Refunded"),
            ("CHARGEBACK", "Chargeback"),
            ("EXPIRED", "Expired"),
        ]
    )

    # Enhanced existing fields
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    txn_type = models.CharField(max_length=15, choices=TXN_TYPES)

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="USD"
    )

    status = models.CharField(
        max_length=20,
        choices=TXN_STATUS,
        default="PENDING"
    )

    def generate_transaction_reference():
        """Generate a unique transaction reference"""
        return f"TXN-{uuid.uuid4().hex[:8].upper()}"

    reference = models.CharField(
        max_length=120,
        unique=True,
        default=generate_transaction_reference
    )

    description = models.TextField(blank=True, null=True)

    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=PAYMENT_METHODS
    )

    # Enhanced foreign key relations
    from_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="sent_transactions"
    )

    to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="received_transactions"
    )

    # Parent transaction for refunds/chargebacks
    parent_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='child_transactions'
    )

    # Link to trade post (for trade-related transactions)
    trade_post = models.ForeignKey('SocialPost', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='trade_transactions')

    # Enhanced metadata fields
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured data for payment details, user info, etc."
    )

    # Enhanced timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    # Enhanced financial fields
    balance_before = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True
    )

    balance_after = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True
    )

    fee_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name="Processing Fee"
    )

    net_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Net Amount (Amount - Fee)"
    )

    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Exchange rate used for currency conversion"
    )

    converted_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Amount in base currency"
    )

    # Enhanced admin/audit fields
    admin_notes = models.TextField(blank=True, null=True)
    is_flagged = models.BooleanField(default=False)
    flagged_reason = models.TextField(blank=True, null=True)

    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="User IP Address"
    )

    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name="User Browser/Device Info"
    )

    country = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="ISO 3166-1 alpha-2 country code"
    )

    # Webhook/automation fields
    webhook_attempts = models.PositiveIntegerField(default=0)
    last_webhook_sent = models.DateTimeField(blank=True, null=True)
    webhook_response = models.JSONField(default=dict, blank=True)

    # New admin fields
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_transactions"
    )

    approved_at = models.DateTimeField(blank=True, null=True)

    # KYC check flag
    kyc_checked = models.BooleanField(default=False)
    kyc_required = models.BooleanField(default=False)

    # Custom manager
    objects = models.Manager()

    class StatusManager(models.Manager):
        """Custom manager for filtering by status"""

        def completed(self):
            return self.filter(status="COMPLETED")

        def pending(self):
            return self.filter(status__in=["PENDING", "PROCESSING"])

        def failed(self):
            return self.filter(status__in=["FAILED", "CANCELLED", "EXPIRED"])

        def recent(self, days=7):
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            return self.filter(created_at__gte=cutoff_date)

        def by_user(self, user):
            return self.filter(user=user)

        def pending_admin_approval(self):
            return self.filter(
                status__in=["PENDING", "PROCESSING"],
                txn_type__in=["WITHDRAW", "TRANSFER"]
            )

    status_manager = StatusManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['txn_type']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['payment_gateway']),
            models.Index(fields=['created_at', 'status']),
        ]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.reference} - {self.user.username} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Auto-calculate net amount
        if self.amount is not None and self.fee_amount is not None:
            self.net_amount = self.amount - self.fee_amount

        # Set completion time when status changes to COMPLETED
        if self.pk:
            try:
                old_instance = Transaction.objects.get(pk=self.pk)
                if old_instance.status != "COMPLETED" and self.status == "COMPLETED":
                    self.completed_at = timezone.now()
            except Transaction.DoesNotExist:
                pass

        # Set expiry for pending transactions (24 hours)
        if self.status == "PENDING" and not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)

        super().save(*args, **kwargs)

    @property
    def is_completed(self):
        return self.status == "COMPLETED"

    @property
    def is_pending(self):
        return self.status in ["PENDING", "PROCESSING"]

    @property
    def is_failed(self):
        return self.status in ["FAILED", "CANCELLED", "EXPIRED"]

    @property
    def display_status(self):
        """Get user-friendly status display"""
        status_map = {
            "PENDING": "Pending",
            "PROCESSING": "Processing",
            "COMPLETED": "Completed",
            "FAILED": "Failed",
            "CANCELLED": "Cancelled",
            "ON_HOLD": "On Hold",
            "REFUNDED": "Refunded",
            "PARTIAL": "Partially Completed",
            "EXPIRED": "Expired",
        }
        return status_map.get(self.status, self.status)

    @property
    def is_transfer(self):
        return self.txn_type == "TRANSFER"

    @property
    def counterparty(self):
        """Get the other party in transfer transactions"""
        if self.from_user and self.to_user:
            if self.user == self.from_user:
                return self.to_user
            else:
                return self.from_user
        return None

    def mark_as_processing(self):
        """Mark transaction as processing"""
        self.status = "PROCESSING"
        self.save()

    def mark_as_completed(self):
        """Mark transaction as completed"""
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.save()

    def mark_as_failed(self, reason=""):
        """Mark transaction as failed"""
        self.status = "FAILED"
        self.description = f"{self.description or ''} | Failed: {reason}".strip()
        self.save()

    def process_refund(self, refund_amount=None, admin_user=None, reason=""):
        """Process refund for this transaction"""
        if self.status != "COMPLETED":
            raise ValueError("Only completed transactions can be refunded")

        refund_amount = refund_amount or self.amount

        # Create refund transaction
        refund_txn = Transaction.objects.create(
            user=self.user,
            txn_type="REFUND",
            amount=refund_amount,
            currency=self.currency,
            status="PENDING",
            description=f"Refund for {self.reference}: {reason}",
            parent_transaction=self,
            metadata={
                'original_transaction': str(self.transaction_id),
                'refund_reason': reason,
                'admin': admin_user.username if admin_user else 'system'
            }
        )

        return refund_txn

    def get_absolute_url(self):
        """Get URL for transaction detail view"""
        return reverse('transaction_detail', kwargs={'reference': self.reference})

    def check_expiry(self):
        """Check if transaction has expired and update status"""
        if self.status == "PENDING" and self.expires_at and timezone.now() > self.expires_at:
            self.status = "EXPIRED"
            self.save()
            return True
        return False


class SocialPost(models.Model):
    """Community social post model"""
    POST_TYPES = [
        ('analysis', 'Market Analysis'),
        ('trade_idea', 'Trade Idea'),
        ('question', 'Question'),
        ('news', 'Market News'),
        ('education', 'Educational'),
        ('discussion', 'Discussion'),
        ('achievement', 'Achievement'),
        ('review', 'Broker/Service Review'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('followers', 'Followers Only'),
        ('private', 'Private'),
    ]

    TRADE_DIRECTION_CHOICES = [
        ('long', 'Long'),
        ('short', 'Short'),
    ]

    TIMEFRAME_CHOICES = [
        ('1m', '1 Minute'),
        ('5m', '5 Minutes'),
        ('15m', '15 Minutes'),
        ('30m', '30 Minutes'),
        ('1h', '1 Hour'),
        ('4h', '4 Hours'),
        ('1d', '1 Day'),
        ('1w', '1 Week'),
        ('1M', '1 Month'),
    ]

    POST_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_posts')
    content = models.TextField()
    post_type = models.CharField(max_length=50, choices=POST_TYPES, default='discussion')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='public')

    # Trading-specific fields
    trading_symbol = models.CharField(max_length=20, blank=True, null=True)
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, blank=True, null=True)
    target_price = models.DecimalField(max_digits=15, decimal_places=6, blank=True, null=True)
    stop_loss = models.DecimalField(max_digits=15, decimal_places=6, blank=True, null=True)
    trade_direction = models.CharField(
        max_length=10,
        choices=TRADE_DIRECTION_CHOICES,
        blank=True,
        null=True
    )
    timeframe = models.CharField(
        max_length=10,
        choices=TIMEFRAME_CHOICES,
        blank=True,
        null=True
    )
    position_size = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Position Size"
    )
    risk_reward_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    # Trade outcome and P&L
    trade_outcome = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ('win', 'Win'),
            ('loss', 'Loss'),
            ('breakeven', 'Break Even'),
            ('open', 'Still Open'),
        ]
    )
    pnl_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="P&L Amount"
    )
    pnl_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="P&L %"
    )

    # Post status
    post_status = models.CharField(
        max_length=20,
        choices=POST_STATUS_CHOICES,
        default='published'
    )

    # Post engagement metrics
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    bookmarks_count = models.PositiveIntegerField(default=0)

    # Media and attachments
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    video = models.FileField(upload_to='post_videos/', blank=True, null=True)
    link_preview = models.JSONField(default=dict, blank=True)

    # Moderation
    is_pinned = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    reported_count = models.PositiveIntegerField(default=0)
    is_under_review = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)

    # Tags and categories
    tags = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=50, blank=True, null=True)

    # Mentions
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='mentioned_in_posts')

    # Parent post for replies
    parent_post = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['post_type']),
            models.Index(fields=['trading_symbol']),
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['post_status']),
        ]
        verbose_name = "Social Post"
        verbose_name_plural = "Social Posts"

    def __str__(self):
        return f"Post by {self.author.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Handle scheduled posts
        if self.scheduled_for and self.scheduled_for > timezone.now():
            self.is_active = False

        # Update parent post's comment count if this is a reply
        if self.parent_post and not self.pk:
            super().save(*args, **kwargs)
            self.parent_post.update_comment_count()
            return

        # Update edited timestamp
        if self.pk:
            original = SocialPost.objects.get(pk=self.pk)
            if original.content != self.content:
                self.is_edited = True
                self.edited_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_reply(self):
        return self.parent_post is not None

    @property
    def is_trade_idea(self):
        return self.post_type == 'trade_idea'

    @property
    def can_edit(self, user):
        """Check if user can edit this post"""
        if user == self.author:
            # Can edit within 30 minutes of creation
            time_since_creation = timezone.now() - self.created_at
            return time_since_creation.total_seconds() <= 1800  # 30 minutes
        return user.is_staff

    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def update_comment_count(self):
        """Update comment count from related comments"""
        from .models import SocialComment
        self.comments_count = SocialComment.objects.filter(post=self, is_active=True).count()
        self.save(update_fields=['comments_count'])

    def update_like_count(self):
        """Update like count from related likes"""
        from .models import SocialPostLike
        self.likes_count = SocialPostLike.objects.filter(post=self, is_active=True).count()
        self.save(update_fields=['likes_count'])

    def get_absolute_url(self):
        """Get URL for post detail view"""
        return reverse('social_post_detail', kwargs={'pk': self.pk})

    def get_summary(self, length=150):
        """Get truncated summary of content"""
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + '...'

    def get_author_profile(self):
        """Get author's profile"""
        return self.author.profile

    def can_view(self, user):
        """Check if user can view this post"""
        if self.visibility == 'public':
            return True
        if user == self.author:
            return True
        if self.visibility == 'followers':
            return self.author.profile.is_following(user)
        return False

    def report(self, user, reason):
        """Report this post"""
        from .models import Report
        report, created = Report.objects.get_or_create(
            post=self,
            reporter=user,
            defaults={'reason': reason}
        )
        if created:
            self.reported_count += 1
            if self.reported_count >= 5:
                self.is_under_review = True
            self.save()
        return report


class SocialPostLike(models.Model):
    """Post likes model"""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Different like types
    reaction_type = models.CharField(
        max_length=20,
        default='like',
        choices=[
            ('like', 'Like'),
            ('love', 'Love'),
            ('laugh', 'Laugh'),
            ('wow', 'Wow'),
            ('sad', 'Sad'),
            ('angry', 'Angry'),
            ('bullish', 'Bullish'),
            ('bearish', 'Bearish'),
        ]
    )

    class Meta:
        unique_together = ['post', 'user']
        ordering = ['-created_at']
        verbose_name = "Post Like"
        verbose_name_plural = "Post Likes"

    def __str__(self):
        return f"{self.user.username} liked post {self.post.id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update post like count
        self.post.update_like_count()

        # Update author's like count
        profile = self.post.author.profile
        if self.is_active:
            profile.total_likes_received += 1
        else:
            profile.total_likes_received = max(0, profile.total_likes_received - 1)
        profile.save(update_fields=['total_likes_received'])


class SocialComment(models.Model):
    """Post comments model"""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='replies')

    # Engagement metrics
    likes_count = models.PositiveIntegerField(default=0)
    replies_count = models.PositiveIntegerField(default=0)

    # Moderation
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    reported_count = models.PositiveIntegerField(default=0)

    # Mentions
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='mentioned_in_comments')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['author', 'created_at']),
        ]
        verbose_name = "Social Comment"
        verbose_name_plural = "Social Comments"

    def __str__(self):
        return f"Comment by {self.author.username} on post {self.post.id}"

    def save(self, *args, **kwargs):
        # Update parent comment's reply count if this is a reply
        if self.parent_comment and not self.pk:
            super().save(*args, **kwargs)
            self.parent_comment.replies_count += 1
            self.parent_comment.save(update_fields=['replies_count'])
            return

        # Update edited timestamp
        if self.pk:
            original = SocialComment.objects.get(pk=self.pk)
            if original.content != self.content:
                self.is_edited = True
                self.edited_at = timezone.now()

        super().save(*args, **kwargs)

        # Update post comment count
        if not self.parent_comment:  # Only top-level comments affect post count
            self.post.update_comment_count()

        # Update author's comment count
        profile = self.author.profile
        if self.is_active:
            profile.total_comments += 1
        else:
            profile.total_comments = max(0, profile.total_comments - 1)
        profile.save(update_fields=['total_comments'])

    @property
    def is_reply(self):
        return self.parent_comment is not None

    def get_summary(self, length=100):
        """Get truncated summary of comment"""
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + '...'

    def can_edit(self, user):
        """Check if user can edit this comment"""
        if user == self.author:
            # Can edit within 15 minutes of creation
            time_since_creation = timezone.now() - self.created_at
            return time_since_creation.total_seconds() <= 900  # 15 minutes
        return user.is_staff


class FollowRelationship(models.Model):
    """User following/follower relationships"""
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    # Notification preferences for this follow
    notify_on_posts = models.BooleanField(default=True)
    notify_on_trades = models.BooleanField(default=True)

    class Meta:
        unique_together = ['follower', 'followed']
        ordering = ['-created_at']
        verbose_name = "Follow Relationship"
        verbose_name_plural = "Follow Relationships"

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Update follower/following counts
        follower_profile = self.follower.profile
        followed_profile = self.followed.profile

        follower_profile.following_count = FollowRelationship.objects.filter(follower=self.follower).count()
        follower_profile.save(update_fields=['following_count'])

        followed_profile.followers_count = FollowRelationship.objects.filter(followed=self.followed).count()
        followed_profile.save(update_fields=['followers_count'])

    def delete(self, *args, **kwargs):
        # Store IDs for updating counts after deletion
        follower_id = self.follower.id
        followed_id = self.followed.id

        super().delete(*args, **kwargs)

        # Update follower/following counts after deletion
        follower_profile = Profile.objects.get(user_id=follower_id)
        followed_profile = Profile.objects.get(user_id=followed_id)

        follower_profile.following_count = FollowRelationship.objects.filter(follower_id=follower_id).count()
        follower_profile.save(update_fields=['following_count'])

        followed_profile.followers_count = FollowRelationship.objects.filter(followed_id=followed_id).count()
        followed_profile.save(update_fields=['followers_count'])


class Report(models.Model):
    """Content reporting system"""
    REPORT_TYPES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('harassment', 'Harassment'),
        ('false_info', 'False Information'),
        ('trading_fraud', 'Trading Fraud'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('action_taken', 'Action Taken'),
        ('dismissed', 'Dismissed'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')

    # Report target (can be post or comment)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='reports')
    comment = models.ForeignKey(SocialComment, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='reports')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='reports_against')

    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Admin handling
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reports_reviewed')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    action_taken = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self):
        target = self.post or self.comment or self.reported_user
        return f"Report on {target} by {self.reporter.username}"

    @property
    def target(self):
        """Get the target of the report"""
        return self.post or self.comment or self.reported_user

    def review(self, admin_user, notes="", action=""):
        """Mark report as reviewed"""
        self.status = 'reviewed'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.action_taken = action
        self.save()

    def take_action(self, admin_user, action, notes=""):
        """Take action on report"""
        self.status = 'action_taken'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.action_taken = action
        self.admin_notes = notes
        self.save()


class Notification(models.Model):
    """User notification system"""
    NOTIFICATION_TYPES = [
        ('post_like', 'Post Liked'),
        ('post_comment', 'New Comment'),
        ('new_follower', 'New Follower'),
        ('trade_update', 'Trade Update'),
        ('message', 'New Message'),
        ('system', 'System Notification'),
        ('achievement', 'Achievement Unlocked'),
        ('mention', 'You Were Mentioned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Related objects
    related_post = models.ForeignKey(SocialPost, on_delete=models.SET_NULL, null=True, blank=True)
    related_comment = models.ForeignKey(SocialComment, on_delete=models.SET_NULL, null=True, blank=True)
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='caused_notifications')

    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)

    # Delivery status
    email_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.notification_type} for {self.user.username}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    @classmethod
    def create_notification(cls, user, notification_type, title, message, **kwargs):
        """Helper method to create notifications"""
        notification = cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            related_post=kwargs.get('related_post'),
            related_comment=kwargs.get('related_comment'),
            related_user=kwargs.get('related_user')
        )

        # Send email if user has email notifications enabled
        if user.profile.email_notifications:
            notification.send_email()

        return notification

    def send_email(self):
        """Send email notification"""
        # This would integrate with your email service
        # For now, just mark as sent
        self.email_sent = True
        self.save()

    def get_absolute_url(self):
        """Get URL for notification action"""
        if self.related_post:
            return self.related_post.get_absolute_url()
        elif self.related_comment:
            return self.related_comment.post.get_absolute_url()
        return '#'


class Subscriber(models.Model):
    """Newsletter subscriber model"""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    source = models.CharField(
        max_length=50,
        default='website',
        choices=[
            ('website', 'Website'),
            ('signup', 'Signup Form'),
            ('api', 'API'),
            ('import', 'Import'),
            ('other', 'Other'),
        ]
    )
    preferences = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Email verification
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)

    # Engagement tracking
    last_email_sent = models.DateTimeField(blank=True, null=True)
    emails_received = models.PositiveIntegerField(default=0)
    emails_opened = models.PositiveIntegerField(default=0)
    emails_clicked = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = "Subscriber"
        verbose_name_plural = "Subscribers"

    def __str__(self):
        return self.email

    def unsubscribe(self):
        """Unsubscribe the user"""
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()

    def resubscribe(self):
        """Resubscribe the user"""
        self.is_active = True
        self.unsubscribed_at = None
        self.save()

    def verify(self):
        """Verify the subscriber's email"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save()

    def track_email_open(self):
        """Track email open"""
        self.emails_opened += 1
        self.save(update_fields=['emails_opened'])

    def track_email_click(self):
        """Track email click"""
        self.emails_clicked += 1
        self.save(update_fields=['emails_clicked'])

    @property
    def open_rate(self):
        """Calculate email open rate"""
        if self.emails_received == 0:
            return 0
        return (self.emails_opened / self.emails_received) * 100

    @property
    def click_rate(self):
        """Calculate email click rate"""
        if self.emails_received == 0:
            return 0
        return (self.emails_clicked / self.emails_received) * 100


class ChatMessage(models.Model):
    """Direct messaging between users"""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('chart', 'Chart'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages',
                                 null=True, blank=True)
    chat_room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE, null=True, blank=True,
                                  related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()

    # File handling
    file = models.FileField(upload_to='chat_files/%Y/%m/%d/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    # Read status with proper handling
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)

    # Delivery status
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(blank=True, null=True)

    # For WebSocket message tracking
    ws_message_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    # Reply to another message
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='replies')

    # Reactions
    reactions = models.JSONField(default=dict, blank=True)

    # Deletion flags
    deleted_by_sender = models.BooleanField(default=False)
    deleted_by_receiver = models.BooleanField(default=False)
    deleted_for_everyone = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'receiver', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['receiver', 'created_at']),
            models.Index(fields=['is_read', 'created_at']),
            models.Index(fields=['chat_room', 'created_at']),
        ]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    def __str__(self):
        if self.chat_room:
            return f"{self.sender.username} in {self.chat_room.name}: {self.content[:50]}"
        return f"{self.sender.username} → {self.receiver.username if self.receiver else 'Unknown'}: {self.content[:50]}"

    def save(self, *args, **kwargs):
        # Auto-populate file info if file is uploaded
        if self.file and not self.file_name:
            self.file_name = self.file.name
            self.file_size = self.file.size

            # Determine file type
            if self.file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                self.message_type = 'image'
            elif self.file.name.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                self.message_type = 'audio'
            elif self.file.name.lower().endswith(('.mp4', '.avi', '.mov', '.wmv')):
                self.message_type = 'video'
            else:
                self.message_type = 'file'

        # Generate WebSocket message ID if not present
        if not self.ws_message_id:
            self.ws_message_id = f"msg_{uuid.uuid4().hex[:16]}"

        super().save(*args, **kwargs)

    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
            return True
        return False

    def mark_as_delivered(self):
        """Mark message as delivered"""
        if not self.is_delivered:
            self.is_delivered = True
            self.delivered_at = timezone.now()
            self.save()
            return True
        return False

    def add_reaction(self, user, emoji):
        """Add reaction to message"""
        if 'reactions' not in self.reactions:
            self.reactions = {'reactions': {}}

        reactions = self.reactions.get('reactions', {})
        if emoji not in reactions:
            reactions[emoji] = []

        if user.id not in reactions[emoji]:
            reactions[emoji].append(user.id)
            self.save()

    def remove_reaction(self, user, emoji):
        """Remove reaction from message"""
        if 'reactions' in self.reactions and emoji in self.reactions.get('reactions', {}):
            if user.id in self.reactions['reactions'][emoji]:
                self.reactions['reactions'][emoji].remove(user.id)
                if not self.reactions['reactions'][emoji]:
                    del self.reactions['reactions'][emoji]
                self.save()

    def to_dict(self):
        """Convert message to dictionary for API/WebSocket"""
        return {
            'id': str(self.id),
            'ws_message_id': self.ws_message_id,
            'sender': {
                'id': self.sender.id,
                'username': self.sender.username,
                'display_name': self.sender.profile.get_display_name(),
                'avatar': self.sender.profile.get_avatar_url(),
            },
            'receiver': {
                'id': self.receiver.id if self.receiver else None,
                'username': self.receiver.username if self.receiver else None,
            },
            'content': self.content,
            'message_type': self.message_type,
            'file_url': self.file.url if self.file else None,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_delivered': self.is_delivered,
            'reactions': self.reactions,
            'reply_to': self.reply_to.ws_message_id if self.reply_to else None,
            'timestamp': self.created_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'formatted_time': self.created_at.strftime('%H:%M'),
            'formatted_date': self.created_at.strftime('%Y-%m-%d'),
        }

    @classmethod
    def get_unread_count(cls, user):
        """Get unread message count for a user"""
        return cls.objects.filter(
            receiver=user,
            is_read=False,
            deleted_for_everyone=False
        ).exclude(
            deleted_by_receiver=True
        ).count()


class ChatRoom(models.Model):
    """Chat room for group conversations"""
    ROOM_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('channel', 'Public Channel'),
        ('support', 'Support Room'),
        ('trade', 'Trade Discussion'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='group')

    # Room settings
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    max_members = models.PositiveIntegerField(default=50)

    # Privacy settings
    requires_approval = models.BooleanField(default=False)
    allow_invites = models.BooleanField(default=True)
    allow_uploads = models.BooleanField(default=True)

    # Moderation settings
    allow_edits = models.BooleanField(default=True)
    allow_deletes = models.BooleanField(default=True)
    allow_pinning = models.BooleanField(default=True)

    # Room image/avatar
    avatar = models.ImageField(upload_to='chat_room_avatars/', blank=True, null=True)

    # Members - FIXED: Added through_fields to resolve ambiguity
    members = models.ManyToManyField(
        User,
        through='ChatRoomMember',
        through_fields=('chat_room', 'user'),  # Added this line
        related_name='chat_rooms'
    )

    admins = models.ManyToManyField(User, related_name='admin_chat_rooms', blank=True)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_chat_rooms')

    # Last activity
    last_message = models.ForeignKey('ChatMessage', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='last_message_in_room')
    last_activity = models.DateTimeField(blank=True, null=True)

    # Statistics
    message_count = models.PositiveIntegerField(default=0)
    member_count = models.PositiveIntegerField(default=0)

    # Metadata
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ... rest of the ChatRoom model remains the same ...

    class Meta:
        ordering = ['-last_activity', '-created_at']
        indexes = [
            models.Index(fields=['room_type', 'is_active']),
            models.Index(fields=['is_public', 'is_active']),
            models.Index(fields=['creator', 'created_at']),
        ]
        verbose_name = "Chat Room"
        verbose_name_plural = "Chat Rooms"

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    def save(self, *args, **kwargs):
        # Update member count
        if self.pk:
            self.member_count = self.members.count()

        # Update last activity if there's a new last message
        if self.last_message and (not self.last_activity or self.last_message.created_at > self.last_activity):
            self.last_activity = self.last_message.created_at

        super().save(*args, **kwargs)

    @property
    def display_name(self):
        """Get display name for the room"""
        if self.room_type == 'direct' and self.member_count == 2:
            # For direct messages, show other user's name
            other_member = self.members.exclude(id=self.creator.id).first()
            if other_member:
                return other_member.profile.get_display_name()
        return self.name

    @property
    def is_direct_message(self):
        return self.room_type == 'direct'

    @property
    def is_group_chat(self):
        return self.room_type == 'group'

    @property
    def is_full(self):
        return self.member_count >= self.max_members

    def add_member(self, user, added_by=None, role='member'):
        """Add a member to the chat room"""
        if self.is_full:
            raise ValueError("Chat room is full")

        if not self.members.filter(id=user.id).exists():
            ChatRoomMember.objects.create(
                chat_room=self,
                user=user,
                role=role,
                added_by=added_by or self.creator
            )
            self.member_count += 1
            self.save(update_fields=['member_count'])

    def remove_member(self, user, removed_by=None):
        """Remove a member from the chat room"""
        if self.members.filter(id=user.id).exists():
            ChatRoomMember.objects.filter(chat_room=self, user=user).delete()
            self.member_count -= 1
            self.save(update_fields=['member_count'])

            # If this is a direct message room and we remove one member, archive it
            if self.room_type == 'direct' and self.member_count < 2:
                self.is_archived = True
                self.save(update_fields=['is_archived'])

    def promote_to_admin(self, user, promoted_by):
        """Promote a member to admin"""
        if promoted_by in self.admins.all() or promoted_by == self.creator:
            if user not in self.admins.all():
                self.admins.add(user)

                # Update their ChatRoomMember role
                member = ChatRoomMember.objects.filter(chat_room=self, user=user).first()
                if member:
                    member.role = 'admin'
                    member.save()
                return True
        return False

    def demote_from_admin(self, user, demoted_by):
        """Demote an admin to regular member"""
        if demoted_by in self.admins.all() or demoted_by == self.creator:
            if user in self.admins.all() and user != self.creator:
                self.admins.remove(user)

                # Update their ChatRoomMember role
                member = ChatRoomMember.objects.filter(chat_room=self, user=user).first()
                if member:
                    member.role = 'member'
                    member.save()
                return True
        return False

    def can_user_join(self, user):
        """Check if a user can join this room"""
        if not self.is_active or self.is_archived:
            return False

        if self.is_full:
            return False

        if self.requires_approval and not self.members.filter(id=user.id).exists():
            return False

        return True

    def can_user_send_message(self, user):
        """Check if a user can send messages in this room"""
        if not self.members.filter(id=user.id).exists():
            return False

        if self.is_archived:
            return False

        member = ChatRoomMember.objects.filter(chat_room=self, user=user).first()
        if member and member.is_muted:
            return False

        return True

    def update_last_message(self, message):
        """Update the last message in the room"""
        self.last_message = message
        self.last_activity = message.created_at
        self.message_count += 1
        self.save(update_fields=['last_message', 'last_activity', 'message_count'])

    def get_recent_messages(self, limit=50):
        """Get recent messages in the room"""
        return ChatMessage.objects.filter(chat_room=self).order_by('-created_at')[:limit]

    def get_unread_count_for_user(self, user):
        """Get unread message count for a specific user in this room"""
        member = ChatRoomMember.objects.filter(chat_room=self, user=user).first()
        if member:
            return member.unread_count
        return 0

    def mark_as_read_for_user(self, user):
        """Mark all messages as read for a user in this room"""
        member = ChatRoomMember.objects.filter(chat_room=self, user=user).first()
        if member:
            member.unread_count = 0
            member.last_read = timezone.now()
            member.save()

    @classmethod
    def get_or_create_direct_chat(cls, user1, user2):
        """Get or create a direct message chat between two users"""
        # Check if a direct chat already exists between these users
        existing_room = cls.objects.filter(
            room_type='direct',
            members=user1
        ).filter(
            members=user2
        ).filter(
            member_count=2
        ).first()

        if existing_room:
            return existing_room

        # Create new direct chat room
        room = cls.objects.create(
            name=f"Chat between {user1.username} and {user2.username}",
            room_type='direct',
            is_public=False,
            creator=user1,
            max_members=2
        )

        # Add both users as members using ChatRoomMember
        ChatRoomMember.objects.create(chat_room=room, user=user1, role='member')
        ChatRoomMember.objects.create(chat_room=room, user=user2, role='member')

        # Update member count
        room.member_count = 2
        room.save()

        return room


class ChatRoomMember(models.Model):
    """Model for chat room membership with additional info"""
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
        ('guest', 'Guest'),
    ]

    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='room_memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')

    # Member settings
    is_muted = models.BooleanField(default=False)
    notifications_enabled = models.BooleanField(default=True)

    # Activity tracking
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(blank=True, null=True)
    last_read = models.DateTimeField(blank=True, null=True)

    # Message tracking
    unread_count = models.PositiveIntegerField(default=0)

    # Invitation info - FIXED: Made these fields optional
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_members'
    )

    # Removed approved_by field since it's redundant with invited_by

    # Nickname in this room
    nickname = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ['chat_room', 'user']
        ordering = ['-joined_at']
        verbose_name = "Chat Room Member"
        verbose_name_plural = "Chat Room Members"

    # ... rest of the ChatRoomMember model remains the same ...

    def __str__(self):
        return f"{self.user.username} in {self.chat_room.name}"

    @property
    def display_name(self):
        """Get display name for this member in the room"""
        return self.nickname or self.user.profile.get_display_name()

    @property
    def is_admin(self):
        """Check if member is an admin"""
        return self.role in ['owner', 'admin', 'moderator']

    def can_manage_messages(self):
        """Check if member can manage messages (edit/delete/pin)"""
        return self.role in ['owner', 'admin', 'moderator']

    def can_manage_members(self):
        """Check if member can manage other members"""
        return self.role in ['owner', 'admin']

    def can_manage_room(self):
        """Check if member can manage room settings"""
        return self.role in ['owner']

    def update_last_seen(self):
        """Update last seen timestamp"""
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])

    def increment_unread_count(self):
        """Increment unread message count"""
        self.unread_count += 1
        self.save(update_fields=['unread_count'])

    def reset_unread_count(self):
        """Reset unread message count"""
        self.unread_count = 0
        self.last_read = timezone.now()
        self.save(update_fields=['unread_count', 'last_read'])



class BroadcastMessage(models.Model):
    """System broadcast messages to all users"""
    BROADCAST_TYPES = [
        ('system', 'System Announcement'),
        ('maintenance', 'Maintenance Notice'),
        ('update', 'Platform Update'),
        ('promotion', 'Promotion'),
        ('alert', 'Security Alert'),
        ('news', 'Market News'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    broadcast_type = models.CharField(max_length=20, choices=BROADCAST_TYPES, default='system')

    # Target audience
    target_audience = models.CharField(
        max_length=20,
        choices=[
            ('all', 'All Users'),
            ('kyc_verified', 'KYC Verified Users'),
            ('premium', 'Premium Users Only'),
            ('specific_plan', 'Specific Plan'),
        ],
        default='all'
    )

    # For specific plan targeting
    target_plan = models.CharField(
        max_length=50,
        choices=Profile.PLAN_CHOICES,
        blank=True,
        null=True
    )

    # Delivery settings
    is_published = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    # Attachments
    attachment = models.FileField(upload_to='broadcast_attachments/', blank=True, null=True)
    image = models.ImageField(upload_to='broadcast_images/', blank=True, null=True)

    # Stats
    sent_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)

    # Creator
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='created_broadcasts')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_published', 'created_at']),
            models.Index(fields=['broadcast_type']),
            models.Index(fields=['target_audience']),
        ]
        verbose_name = "Broadcast Message"
        verbose_name_plural = "Broadcast Messages"

    def __str__(self):
        return f"{self.title} - {self.broadcast_type}"

    @property
    def is_active(self):
        """Check if broadcast is currently active"""
        now = timezone.now()
        if not self.is_published:
            return False
        if self.scheduled_for and now < self.scheduled_for:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True

    @property
    def read_rate(self):
        """Calculate read rate percentage"""
        if self.sent_count == 0:
            return 0
        return (self.read_count / self.sent_count) * 100

    @property
    def click_rate(self):
        """Calculate click rate percentage"""
        if self.sent_count == 0:
            return 0
        return (self.click_count / self.sent_count) * 100

    def publish(self):
        """Publish the broadcast"""
        self.is_published = True
        self.published_at = timezone.now()

        # Count users who will receive this
        self.sent_count = self.get_target_users().count()
        self.save()

    def unpublish(self):
        """Unpublish the broadcast"""
        self.is_published = False
        self.save()

    def get_target_users(self):
        """Get users who should receive this broadcast"""
        users = User.objects.filter(is_active=True)

        if self.target_audience == 'kyc_verified':
            users = users.filter(profile__kyc_verified=True)
        elif self.target_audience == 'premium':
            users = users.filter(profile__plan__in=['Premium', 'Enterprise'])
        elif self.target_audience == 'specific_plan' and self.target_plan:
            users = users.filter(profile__plan=self.target_plan)

        return users

    def increment_read_count(self):
        """Increment read count"""
        self.read_count += 1
        self.save(update_fields=['read_count'])

    def increment_click_count(self):
        """Increment click count"""
        self.click_count += 1
        self.save(update_fields=['click_count'])

    def should_user_receive(self, user):
        """Check if a specific user should receive this broadcast"""
        if not self.is_active:
            return False

        if self.target_audience == 'all':
            return True
        elif self.target_audience == 'kyc_verified':
            return user.profile.kyc_verified
        elif self.target_audience == 'premium':
            return user.profile.plan in ['Premium', 'Enterprise']
        elif self.target_audience == 'specific_plan' and self.target_plan:
            return user.profile.plan == self.target_plan

        return False

    def get_summary(self, length=100):
        """Get truncated summary of content"""
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + '...'


class UserStatus(models.Model):
    """Track user online status and typing status"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_status')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    typing_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='being_typed_to'
    )
    typing_room = models.ForeignKey(
        'ChatRoom',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='typing_users'
    )

    class Meta:
        verbose_name_plural = 'User statuses'

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"

    def update_online_status(self, is_online=True):
        self.is_online = is_online
        self.last_seen = timezone.now()
        self.save()

    def update_typing_status(self, typing_to=None, typing_room=None):
        self.typing_to = typing_to
        self.typing_room = typing_room
        self.save()

    def clear_typing_status(self):
        self.typing_to = None
        self.typing_room = None
        self.save()

    @property
    def is_typing(self):
        return self.typing_to is not None or self.typing_room is not None



Follow = FollowRelationship
Post = SocialPost
Comment = SocialComment
Like = SocialPostLike
Message = ChatMessage
MessageRoom = ChatRoom