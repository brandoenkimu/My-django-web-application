# forms.py - FIXED VERSION
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import KYCApplication, Transaction, Profile, Subscriber, SocialPost, SocialComment
from django.contrib.auth.models import User
import uuid
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class KYCForm(forms.ModelForm):
    """KYC Form matching the updated model"""
    class Meta:
        model = KYCApplication
        fields = [
            'full_name', 'date_of_birth', 'nationality',
            'address', 'city', 'state', 'postal_code', 'country',
            'document_type', 'document_number',
            'document_issue_date', 'document_expiry_date',
            'document_front', 'document_back',
            'selfie_with_document', 'proof_of_address'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'document_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'document_expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'document_front': forms.FileInput(attrs={'class': 'form-control'}),
            'document_back': forms.FileInput(attrs={'class': 'form-control'}),
            'selfie_with_document': forms.FileInput(attrs={'class': 'form-control'}),
            'proof_of_address': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_document_expiry_date(self):
        expiry_date = self.cleaned_data.get('document_expiry_date')
        issue_date = self.cleaned_data.get('document_issue_date')

        if expiry_date and issue_date and expiry_date <= issue_date:
            raise ValidationError("Expiry date must be after issue date.")

        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError("Document has expired.")

        return expiry_date

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = (timezone.now().date() - dob).days / 365.25
            if age < 18:
                raise ValidationError("You must be at least 18 years old.")
        return dob


class DepositForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "currency", "payment_method"]

    # Payment method choices
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('paypal', 'PayPal'),
        ('alipay', 'Alipay'),
        ('mastercard', 'MasterCard'),
        ('visa', 'Visa'),
    ]

    # Currency choices
    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - British Pound'),
        ('KES', 'KES - Kenyan Shilling'),
        ('CNY', 'CNY - Chinese Yuan'),
    ]

    # Amount presets
    AMOUNT_CHOICES = [
        ('10', '$10'),
        ('20', '$20'),
        ('50', '$50'),
        ('100', '$100'),
        ('250', '$250'),
        ('500', '$500'),
        ('custom', 'Custom Amount'),
    ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Set initial values
        self.fields['currency'].initial = 'USD'

        # Add custom attributes for JavaScript interaction
        self.fields['payment_method'].widget.attrs.update({
            'class': 'form-select payment-method-select',
            'onchange': 'togglePaymentDetails()'
        })
        self.fields['currency'].widget.attrs.update({
            'class': 'form-select currency-select',
            'onchange': 'updateAmountPresets()'
        })

    amount = forms.ChoiceField(
        choices=AMOUNT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'amount-preset', 'onchange': 'toggleCustomAmount()'}),
        initial='50'
    )

    custom_amount = forms.DecimalField(
        required=False,
        min_value=1,
        max_value=10000,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount',
            'style': 'display: none;'
        })
    )

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # M-Pesa specific fields
    mpesa_phone = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '2547XXXXXXXX',
            'style': 'display: none;'
        })
    )

    # Card payment fields
    card_number = forms.CharField(
        required=False,
        max_length=19,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'style': 'display: none;'
        })
    )

    card_expiry = forms.CharField(
        required=False,
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY',
            'style': 'display: none;'
        })
    )

    card_cvv = forms.CharField(
        required=False,
        max_length=4,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'CVV',
            'style': 'display: none;'
        })
    )

    card_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Name on Card',
            'style': 'display: none;'
        })
    )

    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        error_messages={'required': 'You must accept the terms and conditions'}
    )

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        amount_choice = cleaned_data.get('amount')

        # FIXED: Handle None or empty amount_choice
        if not amount_choice:
            self.add_error('amount', 'Please select an amount')
            return cleaned_data

        # Determine final amount
        if amount_choice == 'custom':
            custom_amount = cleaned_data.get('custom_amount')
            if not custom_amount:
                self.add_error('custom_amount', 'Please enter a custom amount')
            elif custom_amount < 1:
                self.add_error('custom_amount', 'Amount must be at least 1')
            elif custom_amount > 10000:
                self.add_error('custom_amount', 'Amount cannot exceed 10,000')
            else:
                cleaned_data['final_amount'] = custom_amount
        else:
            # FIXED: Check if amount_choice can be converted to float
            try:
                cleaned_data['final_amount'] = float(amount_choice)
            except (ValueError, TypeError):
                self.add_error('amount', 'Please select a valid amount')

        # Payment method specific validation
        if payment_method == 'mpesa':
            phone = cleaned_data.get('mpesa_phone')
            if not phone:
                self.add_error('mpesa_phone', 'Phone number is required for M-Pesa')
            elif not phone.startswith('254') or len(phone) != 12:
                self.add_error('mpesa_phone', 'Enter a valid Kenyan phone number (2547XXXXXXXX)')

        elif payment_method in ['mastercard', 'visa']:
            card_number = cleaned_data.get('card_number')
            card_expiry = cleaned_data.get('card_expiry')
            card_cvv = cleaned_data.get('card_cvv')
            card_name = cleaned_data.get('card_name')

            if not card_number:
                self.add_error('card_number', 'Card number is required')
            else:
                # Basic card validation
                card_number = card_number.replace(' ', '')
                if not card_number.isdigit():
                    self.add_error('card_number', 'Card number must contain only digits')
                elif len(card_number) < 15 or len(card_number) > 16:
                    self.add_error('card_number', 'Enter a valid card number')

            if not card_expiry:
                self.add_error('card_expiry', 'Expiry date is required')
            else:
                try:
                    month, year = card_expiry.split('/')
                    month = int(month)
                    year = int(year)

                    if month < 1 or month > 12:
                        self.add_error('card_expiry', 'Invalid month')
                    elif year < 23 or year > 40:  # Assuming current year is 2023
                        self.add_error('card_expiry', 'Invalid year')
                except:
                    self.add_error('card_expiry', 'Format: MM/YY')

            if not card_cvv:
                self.add_error('card_cvv', 'CVV is required')
            elif not card_cvv.isdigit() or len(card_cvv) not in [3, 4]:
                self.add_error('card_cvv', 'Enter a valid CVV')

            if not card_name:
                self.add_error('card_name', 'Name on card is required')

        # Currency validation
        currency = cleaned_data.get('currency')
        if currency == 'KES' and payment_method not in ['mpesa', 'mastercard', 'visa']:
            self.add_error('payment_method', 'KES is only supported for M-Pesa and card payments')

        if currency == 'CNY' and payment_method != 'alipay':
            self.add_error('payment_method', 'CNY is only supported for Alipay')

        return cleaned_data

    def save(self, commit=True):
        # Get the cleaned data
        cleaned_data = self.cleaned_data
        payment_method = cleaned_data.get('payment_method')
        final_amount = cleaned_data.get('final_amount')
        currency = cleaned_data.get('currency')

        # Create transaction instance
        obj = super().save(commit=False)

        # Set transaction properties
        obj.user = self.user
        obj.txn_type = "DEPOSIT"
        obj.reference = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        obj.amount = final_amount
        obj.currency = currency
        obj.payment_method = payment_method
        obj.status = "PENDING"  # Will be updated by payment gateway

        # Store metadata based on payment method
        metadata = {}

        if payment_method == 'mpesa':
            metadata['phone_number'] = cleaned_data.get('mpesa_phone')
            metadata['payment_gateway'] = 'mpesa'

        elif payment_method in ['mastercard', 'visa']:
            card_number = cleaned_data.get('card_number', '').replace(' ', '')
            metadata['card_last_four'] = card_number[-4:] if len(card_number) >= 4 else ''
            metadata['card_name'] = cleaned_data.get('card_name', '')
            metadata['card_expiry'] = cleaned_data.get('card_expiry', '')
            metadata['payment_gateway'] = 'stripe'  # Assuming Stripe for card processing

        elif payment_method == 'paypal':
            metadata['payment_gateway'] = 'paypal'

        elif payment_method == 'alipay':
            metadata['payment_gateway'] = 'alipay'

        # Store metadata in the transaction
        obj.metadata = metadata

        if commit:
            obj.save()

            # Process payment (this would call your payment gateway functions)
            # In a real implementation, this might be done in the view or via signals
            self.process_payment(obj, cleaned_data)

        return obj

    def process_payment(self, transaction, cleaned_data):
        """
        This method would initiate the payment process with the selected gateway.
        In a production environment, this should be done asynchronously (Celery task).
        """
        # Import payment gateways (commented out as they may not exist yet)
        # from .payment_gateways import (
        #     process_mpesa_payment,
        #     process_paypal_payment,
        #     process_alipay_payment,
        #     process_card_payment
        # )

        payment_data = {
            'amount': float(transaction.amount),
            'currency': transaction.currency,
            'transaction_id': str(transaction.transaction_id),
            'user_email': transaction.user.email,
            'reference': transaction.reference,
        }

        # Add method-specific data
        if transaction.payment_method == 'mpesa':
            payment_data['phone_number'] = cleaned_data.get('mpesa_phone')
            # result = process_mpesa_payment(payment_data)

        elif transaction.payment_method == 'paypal':
            # result = process_paypal_payment(payment_data)
            pass

        elif transaction.payment_method == 'alipay':
            # result = process_alipay_payment(payment_data)
            pass

        elif transaction.payment_method in ['mastercard', 'visa']:
            payment_data.update({
                'card_number': cleaned_data.get('card_number'),
                'expiry_date': cleaned_data.get('card_expiry'),
                'cvv': cleaned_data.get('card_cvv'),
                'card_name': cleaned_data.get('card_name')
            })
            # result = process_card_payment(payment_data)

        # Note: In production, this should be async or handled differently
        # transaction.save()  # Update with result

    def get_payment_fields(self):
        """
        Return which payment fields should be displayed based on selected method
        """
        payment_method = self.data.get('payment_method') or self.initial.get('payment_method')

        fields = {
            'mpesa': ['mpesa_phone'],
            'mastercard': ['card_number', 'card_expiry', 'card_cvv', 'card_name'],
            'visa': ['card_number', 'card_expiry', 'card_cvv', 'card_name'],
            'paypal': [],
            'alipay': [],
        }

        return fields.get(payment_method, [])


class WithdrawForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "currency"]

    def save(self, user, commit=True):
        obj = super().save(commit=False)
        obj.user = user
        obj.txn_type = "WITHDRAW"
        obj.reference = f"WDR-{uuid.uuid4().hex[:12]}"
        if commit:
            obj.save()
        return obj


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", 'first_name', 'last_name']
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["phone", "country", 'plan', 'bio']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'plan': forms.Select(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Country choices
        self.fields['country'].choices = [
            ('', 'Select Country'),
            ('US', 'United States'),
            ('UK', 'United Kingdom'),
            ('CA', 'Canada'),
            ('AU', 'Australia'),
            ('NG', 'Nigeria'),
            ('KE', 'Kenya'),
            ('ZA', 'South Africa'),
            ('GH', 'Ghana'),
        ]


# Add ProfileForm as an alias to ProfileUpdateForm
# This is what your views.py is trying to import
ProfileForm = ProfileUpdateForm


class SubscriberForm(forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ['name', 'email']  # Or just ['email'] if you want to remove the name field
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Email Address'
            })
        }


class PostForm(forms.ModelForm):
    class Meta:
        model = SocialPost
        fields = [
            'content', 'post_type', 'visibility', 'image', 'video',
            'trading_symbol', 'entry_price', 'target_price', 'stop_loss',
            'trade_direction', 'timeframe', 'position_size', 'risk_reward_ratio',
            'category', 'tags'
        ]
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Share your trading idea, analysis, or market insight...',
                'class': 'form-control',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*',
            }),
            'post_type': forms.Select(attrs={'class': 'form-select'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'trading_symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., BTC/USD, AAPL, EURUSD',
            }),
            'entry_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Entry Price',
                'step': '0.0001',
            }),
            'target_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Target Price',
                'step': '0.0001',
            }),
            'stop_loss': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Stop Loss',
                'step': '0.0001',
            }),
            'trade_direction': forms.Select(attrs={'class': 'form-select'}),
            'timeframe': forms.Select(attrs={'class': 'form-select'}),
            'position_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Position Size',
                'step': '0.0001',
            }),
            'risk_reward_ratio': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Risk/Reward Ratio',
                'step': '0.01',
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category (optional)',
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tags (comma separated)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make content required
        self.fields['content'].required = True

        # Convert tags list to comma-separated string for display
        if self.instance and self.instance.tags:
            self.initial['tags'] = ', '.join(self.instance.tags)

    def clean_tags(self):
        """Convert comma-separated tags to list"""
        tags = self.cleaned_data.get('tags', '')
        if tags:
            return [tag.strip() for tag in tags.split(',') if tag.strip()]
        return []

    def clean(self):
        cleaned_data = super().clean()
        post_type = cleaned_data.get('post_type')

        # Validate trade-specific fields for trade ideas
        if post_type == 'trade_idea':
            trading_symbol = cleaned_data.get('trading_symbol')
            if not trading_symbol:
                self.add_error('trading_symbol', 'Trading symbol is required for trade ideas')

            entry_price = cleaned_data.get('entry_price')
            target_price = cleaned_data.get('target_price')

            if entry_price is not None and target_price is not None:
                if entry_price <= 0:
                    self.add_error('entry_price', 'Entry price must be positive')
                if target_price <= 0:
                    self.add_error('target_price', 'Target price must be positive')

                # Validate target is different from entry
                if entry_price == target_price:
                    self.add_error('target_price', 'Target price must be different from entry price')

        return cleaned_data


class CommentForm(forms.ModelForm):
    class Meta:
        model = SocialComment
        fields = ['content', 'parent_comment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Write your comment...',
                'class': 'form-control',
                'style': 'resize: none;'
            }),
            'parent_comment': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].required = True
        self.fields['parent_comment'].required = False


# At the top of views.py, after imports
from django import forms
from .models import ChatRoom, User, Message, Follow


# Add this class definition BEFORE the create_group_chat view
class GroupChatForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.exclude(id=1),  # Will be overridden in __init__
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Members"
    )

    class Meta:
        model = ChatRoom
        fields = ['name', 'description', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter group name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the group purpose',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Exclude the current user from member choices
            self.fields['members'].queryset = User.objects.exclude(id=user.id)