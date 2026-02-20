# payments/gateways.py
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY
# 1. First, create a simple payment gateway module without external dependencies

# payments/gateways.py
import requests
import json
import base64
import hashlib
from datetime import datetime
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class PaymentGateway:
    """Unified payment gateway handler"""

    @staticmethod
    def process_payment(payment_method, data):
        """Route payment to appropriate gateway"""
        processors = {
            'mpesa': PaymentGateway.process_mpesa,
            'paypal': PaymentGateway.process_paypal,
            'alipay': PaymentGateway.process_alipay,
            'mastercard': PaymentGateway.process_stripe,
            'visa': PaymentGateway.process_stripe,
        }

        processor = processors.get(payment_method.lower())
        if processor:
            return processor(data)
        else:
            return {
                'success': False,
                'error': f'Unsupported payment method: {payment_method}'
            }

    @staticmethod
    def process_mpesa(data):
        """Process M-Pesa payment"""
        try:
            # For development, return mock response
            # In production, implement actual M-Pesa API

            phone = data.get('phone_number', '')
            amount = data.get('amount', 0)

            return {
                'success': True,
                'reference_id': f"MPESA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'message': 'STK Push initiated (Mock for development)',
                'metadata': {
                    'phone': phone,
                    'amount': amount,
                    'currency': 'KES',
                    'gateway': 'mpesa',
                    'status': 'pending'
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_paypal(data):
        """Process PayPal payment"""
        try:
            amount = data.get('amount', 0)
            currency = data.get('currency', 'USD')

            # Mock PayPal response
            return {
                'success': True,
                'redirect_url': f"{getattr(settings, 'BASE_URL', '')}/paypal/mock_redirect/",
                'reference_id': f"PAYPAL-{data.get('transaction_id', '')}",
                'metadata': {
                    'amount': amount,
                    'currency': currency,
                    'gateway': 'paypal',
                    'sandbox': True
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_alipay(data):
        """Process Alipay payment (mock for now)"""
        try:
            amount = data.get('amount', 0)
            currency = data.get('currency', 'CNY')

            # Mock Alipay response
            return {
                'success': True,
                'redirect_url': f"{getattr(settings, 'BASE_URL', '')}/alipay/mock_redirect/",
                'reference_id': f"ALIPAY-{data.get('transaction_id', '')}",
                'metadata': {
                    'amount': amount,
                    'currency': currency,
                    'gateway': 'alipay',
                    'development_mode': True
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_stripe(data):
        """Process Stripe payment (for MasterCard/Visa)"""
        try:
            # Check if stripe is installed
            import stripe

            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

            if not stripe.api_key:
                # Return mock for development
                return {
                    'success': True,
                    'client_secret': f"pi_mock_{data.get('transaction_id', '')}_secret",
                    'reference_id': f"STRIPE-MOCK-{data.get('transaction_id', '')}",
                    'metadata': {
                        'amount': data.get('amount', 0),
                        'currency': data.get('currency', 'usd'),
                        'gateway': 'stripe',
                        'requires_action': False
                    }
                }

            # Real Stripe implementation
            amount = int(float(data.get('amount', 0)) * 100)
            currency = data.get('currency', 'usd').lower()

            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata={
                    'transaction_id': data.get('transaction_id'),
                    'user_email': data.get('user_email', '')
                }
            )

            return {
                'success': True,
                'client_secret': payment_intent.client_secret,
                'reference_id': payment_intent.id,
                'metadata': {
                    'payment_intent_id': payment_intent.id,
                    'amount': amount / 100,
                    'currency': currency,
                    'gateway': 'stripe'
                }
            }

        except ImportError:
            # Stripe not installed, return mock
            return {
                'success': True,
                'client_secret': f"pi_mock_{data.get('transaction_id', '')}_secret",
                'reference_id': f"STRIPE-MOCK-{data.get('transaction_id', '')}",
                'metadata': {
                    'amount': data.get('amount', 0),
                    'currency': data.get('currency', 'usd'),
                    'gateway': 'stripe',
                    'mock': True
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# payments/gateways.py
"""
Custom payment gateway implementations using direct API calls
"""

import requests
import json
import base64
import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlencode
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class BasePaymentGateway:
    """Base class for all payment gateways"""

    def __init__(self):
        self.name = "Base Gateway"

    def process_payment(self, data):
        raise NotImplementedError

    def verify_payment(self, reference_id):
        raise NotImplementedError


class MpesaGateway(BasePaymentGateway):
    """M-Pesa payment gateway using direct API calls"""

    def __init__(self):
        super().__init__()
        self.name = "M-Pesa"
        self.base_url = "https://sandbox.safaricom.co.ke"

    def get_access_token(self):
        """Get M-Pesa OAuth token"""
        try:
            consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
            consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')

            if not consumer_key or not consumer_secret:
                logger.error("M-Pesa credentials not configured")
                return None

            auth_string = f"{consumer_key}:{consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()

            headers = {
                'Authorization': f'Basic {encoded_auth}'
            }

            response = requests.get(
                f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials',
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get('access_token')
            else:
                logger.error(f"M-Pesa token error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"M-Pesa token error: {str(e)}")
            return None

    def process_payment(self, data):
        """Initiate M-Pesa STK Push"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'error': 'Failed to authenticate with M-Pesa'
                }

            phone = data.get('phone_number', '')
            amount = data.get('amount', 0)
            transaction_id = data.get('transaction_id', '')

            # Format phone number (254XXXXXXXXX)
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]

            if not phone.startswith('254'):
                return {
                    'success': False,
                    'error': 'Invalid phone number. Use format: 254XXXXXXXXX'
                }

            # Prepare STK Push request
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            passkey = getattr(settings, 'MPESA_PASSKEY', '')
            shortcode = getattr(settings, 'MPESA_SHORTCODE', '174379')

            password = base64.b64encode(
                f"{shortcode}{passkey}{timestamp}".encode()
            ).decode()

            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone,
                "PartyB": shortcode,
                "PhoneNumber": phone,
                "CallBackURL": f"{getattr(settings, 'BASE_URL', '')}/api/mpesa/callback/",
                "AccountReference": transaction_id[:12],
                "TransactionDesc": "Payment"
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f'{self.base_url}/mpesa/stkpush/v1/processrequest',
                json=payload,
                headers=headers,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200:
                return {
                    'success': True,
                    'reference_id': response_data.get('CheckoutRequestID'),
                    'message': response_data.get('CustomerMessage', 'STK Push sent'),
                    'metadata': response_data
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('errorMessage', 'M-Pesa payment failed')
                }

        except Exception as e:
            logger.error(f"M-Pesa payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class StripeGateway(BasePaymentGateway):
    """Stripe payment gateway"""

    def __init__(self):
        super().__init__()
        self.name = "Stripe"
        # Stripe will be handled separately via their JS SDK

    def process_payment(self, data):
        """Create Stripe PaymentIntent"""
        try:
            import stripe

            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

            if not stripe.api_key:
                return {
                    'success': False,
                    'error': 'Stripe not configured'
                }

            amount = int(float(data.get('amount', 0)) * 100)
            currency = data.get('currency', 'usd').lower()

            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata={
                    'transaction_id': data.get('transaction_id'),
                    'user_email': data.get('user_email', '')
                }
            )

            return {
                'success': True,
                'reference_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'metadata': {
                    'payment_intent_id': payment_intent.id,
                    'amount': amount / 100,
                    'currency': currency
                }
            }

        except ImportError:
            return {
                'success': False,
                'error': 'Stripe SDK not installed'
            }
        except Exception as e:
            logger.error(f"Stripe payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class PayPalGateway(BasePaymentGateway):
    """PayPal payment gateway using direct API"""

    def __init__(self):
        super().__init__()
        self.name = "PayPal"
        self.base_url = "https://api-m.sandbox.paypal.com"

    def get_access_token(self):
        """Get PayPal OAuth token"""
        try:
            client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
            secret = getattr(settings, 'PAYPAL_SECRET', '')

            if not client_id or not secret:
                logger.error("PayPal credentials not configured")
                return None

            auth_string = base64.b64encode(f"{client_id}:{secret}".encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_string}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {'grant_type': 'client_credentials'}

            response = requests.post(
                f'{self.base_url}/v1/oauth2/token',
                headers=headers,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get('access_token')
            else:
                logger.error(f"PayPal token error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"PayPal token error: {str(e)}")
            return None

    def process_payment(self, data):
        """Create PayPal order"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'error': 'Failed to authenticate with PayPal'
                }

            amount = data.get('amount', 0)
            currency = data.get('currency', 'USD')
            transaction_id = data.get('transaction_id', '')

            payload = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": transaction_id[:50],
                    "amount": {
                        "currency_code": currency,
                        "value": str(amount)
                    }
                }],
                "application_context": {
                    "return_url": f"{getattr(settings, 'BASE_URL', '')}/paypal/return/",
                    "cancel_url": f"{getattr(settings, 'BASE_URL', '')}/paypal/cancel/",
                    "brand_name": getattr(settings, 'SITE_NAME', 'Your Site'),
                    "user_action": "PAY_NOW"
                }
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f'{self.base_url}/v2/checkout/orders',
                json=payload,
                headers=headers,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 201:
                # Find approval URL
                approval_url = None
                for link in response_data.get('links', []):
                    if link.get('rel') == 'approve':
                        approval_url = link.get('href')
                        break

                if approval_url:
                    return {
                        'success': True,
                        'redirect_url': approval_url,
                        'reference_id': response_data.get('id'),
                        'metadata': response_data
                    }
                else:
                    return {
                        'success': False,
                        'error': 'No approval URL found'
                    }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', 'PayPal order creation failed')
                }

        except Exception as e:
            logger.error(f"PayPal payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class AlipayGateway(BasePaymentGateway):
    """Alipay gateway using direct API (simplified)"""

    def __init__(self):
        super().__init__()
        self.name = "Alipay"

    def process_payment(self, data):
        """Create Alipay payment link"""
        try:
            # This is a simplified version
            # For production, use Alipay's official API

            amount = data.get('amount', 0)
            currency = data.get('currency', 'CNY')
            transaction_id = data.get('transaction_id', '')

            # Generate a mock payment URL for development
            # In production, this would be a real Alipay URL
            return_url = f"{getattr(settings, 'BASE_URL', '')}/alipay/return/?transaction_id={transaction_id}"

            return {
                'success': True,
                'redirect_url': return_url,
                'reference_id': f"ALIPAY-{transaction_id}",
                'message': 'Redirect to Alipay required',
                'metadata': {
                    'amount': amount,
                    'currency': currency,
                    'gateway': 'alipay',
                    'development_mode': True
                }
            }

        except Exception as e:
            logger.error(f"Alipay payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Payment Gateway Factory
class PaymentGatewayFactory:
    """Factory to create payment gateway instances"""

    @staticmethod
    def create_gateway(gateway_name):
        gateways = {
            'mpesa': MpesaGateway,
            'stripe': StripeGateway,
            'paypal': PayPalGateway,
            'alipay': AlipayGateway,
        }

        gateway_class = gateways.get(gateway_name.lower())
        if gateway_class:
            return gateway_class()
        else:
            raise ValueError(f"Unknown payment gateway: {gateway_name}")