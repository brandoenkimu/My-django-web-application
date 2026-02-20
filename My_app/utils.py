# My_app/utils.py
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


def get_user_balance(user):
    """
    Get the current balance of a user from their wallet
    """
    try:
        return user.wallet.balance
    except:
        # If wallet doesn't exist, create one and return 0
        from .models import Wallet
        wallet, created = Wallet.objects.get_or_create(user=user)
        return wallet.balance


def create_transaction(user, txn_type, amount, currency="USD", description="", **kwargs):
    """
    Helper function to create transactions
    """
    from .models import Transaction

    return Transaction.objects.create(
        user=user,
        txn_type=txn_type,
        amount=amount,
        currency=currency,
        description=description,
        **kwargs
    )


def process_deposit(user, amount, currency="USD", payment_method=None):
    """
    Process a deposit transaction
    """
    from .models import Transaction, Wallet

    # Get user's wallet
    wallet = Wallet.objects.get(user=user)

    # Create transaction
    txn = Transaction.objects.create(
        user=user,
        txn_type="DEPOSIT",
        amount=amount,
        currency=currency,
        payment_method=payment_method,
        status="PENDING",
        description=f"Deposit of {amount} {currency}"
    )

    # Process payment (this would integrate with payment gateway)
    # For now, auto-complete it
    txn.status = "COMPLETED"
    txn.save()

    # Update wallet balance
    wallet.balance += Decimal(str(amount))
    wallet.save()

    return txn


def process_withdrawal(user, amount, currency="USD"):
    """
    Process a withdrawal transaction
    """
    from .models import Transaction, Wallet
    from decimal import Decimal

    # Get user's wallet
    wallet = Wallet.objects.get(user=user)

    # Check sufficient balance
    if wallet.balance < Decimal(str(amount)):
        raise ValueError("Insufficient balance")

    # Create transaction
    txn = Transaction.objects.create(
        user=user,
        txn_type="WITHDRAW",
        amount=amount,
        currency=currency,
        status="PENDING",
        description=f"Withdrawal of {amount} {currency}"
    )

    # Process withdrawal (would integrate with payment system)
    txn.status = "COMPLETED"
    txn.save()

    # Update wallet balance
    wallet.balance -= Decimal(str(amount))
    wallet.save()

    return txn