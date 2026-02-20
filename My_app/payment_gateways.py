# payment_gateways.py
import requests
import json
import base64
from datetime import datetime
from django.conf import settings
import stripe
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe
if hasattr(settings, 'STRIPE_SECRET_KEY'):
    stripe.api_key = settings.STRIPE_SECRET_KEY


def process_mpesa_payment(data):
    """
    Process M-Pesa payment (Sandbox mode)
    Requires MPESA_API_KEY and MPESA_API_SECRET in settings
    """
    try:
        # Mock implementation for development
        # In production, implement actual M-Pesa API calls

        phone = data.get('phone_number', '')
        amount = data.get('amount', 0)

        # Validate phone number format (254XXXXXXXXX)
        if not phone.startswith('254') or len(phone) != 12:
            return {
                'success': False,
                'error': 'Invalid phone number format. Use 254XXXXXXXXX'
            }

        # Simulate successful M-Pesa STK Push
        # In production, you would call the actual M-Pesa API

        logger.info(f"M-Pesa payment initiated: {amount} KES to {phone}")

        return {
            'success': True,
            'reference_id': f"MPESA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'message': 'STK Push sent to your phone',
            'metadata': {
                'phone': phone,
                'amount': amount,
                'currency': 'KES',
                'gateway': 'mpesa',
                'simulated': True  # Remove in production
            }
        }

    except Exception as e:
        logger.error(f"M-Pesa payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def process_paypal_payment(data):
    """
    Process PayPal payment (Sandbox mode)
    """
    try:
        # Mock implementation
        # In production, use PayPal REST API

        amount = data.get('amount', 0)
        currency = data.get('currency', 'USD')

        logger.info(f"PayPal payment initiated: {amount} {currency}")

        # Generate mock PayPal approval URL
        transaction_id = data.get('transaction_id', '')
        return_url = f"{settings.BASE_URL}/paypal/callback/?transaction_id={transaction_id}"

        return {
            'success': True,
            'redirect_url': return_url,
            'reference_id': f"PAYPAL-{transaction_id}",
            'metadata': {
                'amount': amount,
                'currency': currency,
                'gateway': 'paypal',
                'sandbox': True  # Remove in production
            }
        }

    except Exception as e:
        logger.error(f"PayPal payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def process_alipay_payment(data):
    """
    Process Alipay payment (Mock for development)
    """
    try:
        # Mock implementation - replace with actual Alipay SDK
        amount = data.get('amount', 0)
        currency = data.get('currency', 'CNY')

        logger.info(f"Alipay payment initiated: {amount} {currency}")

        transaction_id = data.get('transaction_id', '')

        return {
            'success': True,
            'reference_id': f"ALIPAY-{transaction_id}",
            'message': 'Redirect to Alipay required',
            'metadata': {
                'amount': amount,
                'currency': currency,
                'gateway': 'alipay',
                'mock': True  # Remove when implementing real Alipay
            }
        }

    except Exception as e:
        logger.error(f"Alipay payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def process_card_payment(data):
    """
    Process card payment using Stripe
    """
    try:
        amount = int(float(data.get('amount', 0)) * 100)  # Convert to cents
        currency = data.get('currency', 'usd').lower()

        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata={
                'transaction_id': data.get('transaction_id'),
                'user_email': data.get('user_email'),
                'reference': data.get('reference')
            },
            payment_method_types=['card'],
        )

        return {
            'success': True,
            'reference_id': payment_intent.id,
            'client_secret': payment_intent.client_secret,
            'metadata': {
                'payment_intent_id': payment_intent.id,
                'amount': amount / 100,  # Convert back to dollars
                'currency': currency,
                'gateway': 'stripe',
                'requires_action': payment_intent.status == 'requires_action'
            }
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Card payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def verify_payment(gateway, reference_id):
    """
    Verify payment status with gateway
    """
    try:
        if gateway == 'stripe':
            payment_intent = stripe.PaymentIntent.retrieve(reference_id)
            return {
                'success': payment_intent.status == 'succeeded',
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency
            }
        else:
            # Mock verification for other gateways
            return {
                'success': True,
                'status': 'completed',
                'message': 'Mock verification - implement actual gateway check'
            }

    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }