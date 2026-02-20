# My_app/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Transaction, Wallet
import time
import random
from decimal import Decimal


@shared_task
def process_pending_transactions():
    """Process all pending transactions"""
    pending_transactions = Transaction.objects.filter(
        status__in=['PENDING', 'PROCESSING']
    )

    for transaction in pending_transactions:
        try:
            # Simulate payment processing
            time.sleep(random.uniform(1, 3))

            # For demo purposes, randomly succeed or fail
            if random.random() < 0.8:  # 80% success rate
                transaction.status = 'COMPLETED'
                transaction.completed_at = timezone.now()

                # Update wallet if it's a deposit
                if transaction.txn_type == 'DEPOSIT':
                    wallet, created = Wallet.objects.get_or_create(
                        user=transaction.user,
                        defaults={'balance': Decimal('0'), 'currency': transaction.currency}
                    )
                    wallet.balance += transaction.amount
                    wallet.save()

                    transaction.balance_after = wallet.balance

                # Send email notification
                send_transaction_email.delay(transaction.id)

            else:
                transaction.status = 'FAILED'

            transaction.save()

        except Exception as e:
            print(f"Error processing transaction {transaction.id}: {e}")
            transaction.status = 'FAILED'
            transaction.save()


@shared_task
def send_transaction_email(transaction_id):
    """Send email notification for a transaction"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        subject = f"Transaction {transaction.status}: {transaction.reference}"
        message = f"""
        Transaction Details:

        Reference: {transaction.reference}
        Type: {transaction.txn_type}
        Amount: {transaction.currency} {transaction.amount}
        Status: {transaction.status}
        Date: {transaction.created_at}

        Thank you for using our service!
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.user.email],
            fail_silently=True,
        )

    except Transaction.DoesNotExist:
        print(f"Transaction {transaction_id} not found")
    except Exception as e:
        print(f"Error sending email: {e}")


@shared_task
def process_withdrawal(transaction_id):
    """Process withdrawal transaction"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        if transaction.txn_type != 'WITHDRAWAL':
            return

        # Simulate withdrawal processing
        time.sleep(random.uniform(2, 5))

        # For demo, mark as completed
        transaction.status = 'COMPLETED'
        transaction.completed_at = timezone.now()
        transaction.save()

        # Send email notification
        send_transaction_email.delay(transaction.id)

    except Transaction.DoesNotExist:
        print(f"Withdrawal transaction {transaction_id} not found")
    except Exception as e:
        print(f"Error processing withdrawal: {e}")
        transaction.status = 'FAILED'
        transaction.save()


@shared_task
def cleanup_expired_transactions():
    """Clean up expired transactions"""
    expired_transactions = Transaction.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=['PENDING', 'PROCESSING']
    )

    for transaction in expired_transactions:
        transaction.status = 'EXPIRED'
        transaction.save()
        print(f"Transaction {transaction.id} expired")


@shared_task
def update_wallet_balances():
    """Periodically update wallet balances (for demo purposes)"""
    wallets = Wallet.objects.all()
    for wallet in wallets:
        # In a real app, you would sync with payment gateway
        pass