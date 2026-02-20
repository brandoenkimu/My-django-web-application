import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid
import random
from datetime import timedelta
from .models import Transaction, Wallet, BalanceChange, WebSocketNotification as Notification, TransactionCategory
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class TransactionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection with improved error handling"""
        self.user = self.scope["user"]
        self.user_id = str(self.user.id) if self.user.is_authenticated else None
        self.connection_id = str(uuid.uuid4())

        logger.info(f"Connection attempt - User: {self.user}, Authenticated: {self.user.is_authenticated}")

        if self.user.is_authenticated:
            try:
                # User-specific room
                self.user_group_name = f'user_{self.user_id}'

                # User transaction room
                self.transaction_group_name = f'transactions_user_{self.user_id}'

                # User notifications room
                self.notification_group_name = f'notifications_user_{self.user_id}'

                # Join user group for balance updates
                await self.channel_layer.group_add(
                    self.user_group_name,
                    self.channel_name
                )

                # Join transaction group
                await self.channel_layer.group_add(
                    self.transaction_group_name,
                    self.channel_name
                )

                # Join notifications group
                await self.channel_layer.group_add(
                    self.notification_group_name,
                    self.channel_name
                )

                # Join global transactions room for broadcasts
                await self.channel_layer.group_add(
                    'transactions_global',
                    self.channel_name
                )

                # Join admin notifications if staff
                if self.user.is_staff:
                    await self.channel_layer.group_add(
                        'admin_notifications',
                        self.channel_name
                    )

                    # Join admin control room
                    await self.channel_layer.group_add(
                        'admin_control',
                        self.channel_name
                    )

                await self.accept()

                # Store connection info
                await self.store_connection_info()

                # Send initial data
                await self.send_initial_data()

                # Start checking for pending transactions
                self.pending_task = asyncio.create_task(self.check_pending_transactions())

                # Start notification checker
                self.notification_task = asyncio.create_task(self.check_notifications())

                logger.info(f"WebSocket connected for user: {self.user.username} (ID: {self.user_id})")

            except Exception as e:
                logger.error(f"Error during WebSocket connection: {e}")
                await self.close(code=4000)
        else:
            await self.close(code=4001)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection with cleanup"""
        logger.info(f"WebSocket disconnecting for user: {getattr(self, 'user', 'unknown')}, Code: {close_code}")

        # Cancel background tasks
        if hasattr(self, 'pending_task'):
            self.pending_task.cancel()

        if hasattr(self, 'notification_task'):
            self.notification_task.cancel()

        # Remove connection info
        if hasattr(self, 'user_id'):
            await self.remove_connection_info()

        # Leave all groups
        groups = [
            getattr(self, 'user_group_name', None),
            getattr(self, 'transaction_group_name', None),
            getattr(self, 'notification_group_name', None),
            'transactions_global',
            'admin_notifications',
            'admin_control'
        ]

        for group in filter(None, groups):
            try:
                await self.channel_layer.group_discard(
                    group,
                    self.channel_name
                )
            except Exception as e:
                logger.debug(f"Error leaving group {group}: {e}")

    async def receive(self, text_data):
        """Handle messages from WebSocket with improved validation"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            request_id = data.get('request_id', str(uuid.uuid4()))

            logger.debug(f"Received message: {message_type} from {self.user.username}")

            # Create response wrapper
            response_base = {
                'type': 'response',
                'request_id': request_id,
                'success': True
            }

            try:
                if message_type == 'get_transactions':
                    transactions = await self.get_user_transactions(
                        data.get('limit', 50),
                        data.get('offset', 0),
                        data.get('filters', {})
                    )
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'get_transactions',
                        'data': transactions,
                        'timestamp': timezone.now().isoformat()
                    }))

                elif message_type == 'get_transaction':
                    transaction_id = data.get('transaction_id')
                    if transaction_id:
                        transaction = await self.get_transaction_by_id(transaction_id)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'get_transaction',
                            'data': transaction if transaction else None
                        }))

                elif message_type == 'check_transaction':
                    transaction_id = data.get('transaction_id')
                    if transaction_id:
                        status = await self.check_transaction_status(transaction_id)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'check_transaction',
                            'data': status
                        }))

                elif message_type == 'retry_transaction':
                    transaction_id = data.get('transaction_id')
                    if transaction_id:
                        result = await self.retry_transaction(transaction_id)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'retry_transaction',
                            'data': result
                        }))

                elif message_type == 'get_balance':
                    balance = await self.get_user_balance()
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'get_balance',
                        'data': balance,
                        'timestamp': timezone.now().isoformat()
                    }))

                elif message_type == 'get_balance_history':
                    history = await self.get_balance_history(
                        data.get('limit', 10),
                        data.get('offset', 0)
                    )
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'get_balance_history',
                        'data': history
                    }))

                elif message_type == 'get_notifications':
                    notifications = await self.get_user_notifications(
                        data.get('unread_only', False),
                        data.get('limit', 20)
                    )
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'get_notifications',
                        'data': notifications
                    }))

                elif message_type == 'mark_notification_read':
                    notification_id = data.get('notification_id')
                    if notification_id:
                        success = await self.mark_notification_read(notification_id)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'mark_notification_read',
                            'data': success
                        }))

                elif message_type == 'create_transaction':
                    if not self.user.is_staff:
                        await self.send_error("Permission denied", request_id)
                        return

                    # Admin creating a transaction for a user
                    user_id = data.get('user_id')
                    transaction_data = data.get('transaction', {})

                    if user_id and transaction_data:
                        result = await self.admin_create_transaction(user_id, transaction_data)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'create_transaction',
                            'data': result
                        }))

                elif message_type == 'admin_modify_balance' and self.user.is_staff:
                    # Admin modifying user balance
                    user_id = data.get('user_id')
                    action = data.get('action')
                    amount = data.get('amount')
                    description = data.get('description')

                    if user_id and action and amount and description:
                        result = await self.admin_modify_balance(user_id, action, amount, description)
                        await self.send(text_data=json.dumps({
                            **response_base,
                            'action': 'admin_modify_balance',
                            'data': result
                        }))

                elif message_type == 'admin_get_users' and self.user.is_staff:
                    users = await self.get_users_for_admin(
                        data.get('limit', 50),
                        data.get('offset', 0),
                        data.get('search', '')
                    )
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'admin_get_users',
                        'data': users
                    }))

                elif message_type == 'admin_get_stats' and self.user.is_staff:
                    stats = await self.get_admin_stats()
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'admin_get_stats',
                        'data': stats
                    }))

                elif message_type == 'ping':
                    await self.send(text_data=json.dumps({
                        **response_base,
                        'action': 'pong',
                        'data': {'timestamp': timezone.now().isoformat()}
                    }))

                else:
                    await self.send_error(f"Unknown message type: {message_type}", request_id)

            except Exception as e:
                logger.error(f"Error processing message {message_type}: {e}")
                await self.send_error(str(e), request_id)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await self.send_error("Invalid JSON format", None)
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send_error("Internal server error", None)

    async def send_initial_data(self):
        """Send initial data on connect"""
        try:
            # Gather all initial data concurrently
            transactions_task = self.get_user_transactions(limit=10)
            balance_task = self.get_user_balance()
            history_task = self.get_balance_history(limit=5)
            notifications_task = self.get_user_notifications(unread_only=True, limit=5)
            categories_task = self.get_transaction_categories()

            transactions, balance, history, notifications, categories = await asyncio.gather(
                transactions_task, balance_task, history_task, notifications_task, categories_task,
                return_exceptions=True
            )

            # Handle any errors
            if isinstance(transactions, Exception):
                logger.error(f"Error fetching transactions: {transactions}")
                transactions = []
            if isinstance(balance, Exception):
                logger.error(f"Error fetching balance: {balance}")
                balance = 0.0
            if isinstance(history, Exception):
                logger.error(f"Error fetching history: {history}")
                history = []
            if isinstance(notifications, Exception):
                logger.error(f"Error fetching notifications: {notifications}")
                notifications = []
            if isinstance(categories, Exception):
                logger.error(f"Error fetching categories: {categories}")
                categories = []

            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': {
                    'transactions': transactions,
                    'balance': balance,
                    'balance_history': history,
                    'notifications': notifications,
                    'categories': categories,
                    'user': {
                        'id': self.user.id,
                        'username': self.user.username,
                        'is_staff': self.user.is_staff,
                        'email': self.user.email
                    }
                },
                'timestamp': timezone.now().isoformat()
            }))

        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
            await self.send_error("Failed to load initial data", None)

    async def check_pending_transactions(self):
        """Periodically check and process pending transactions"""
        while True:
            try:
                if not self.user.is_authenticated:
                    break

                pending_txns = await self.get_pending_transactions()

                for txn in pending_txns:
                    # Check if transaction is expired
                    if txn['expires_at'] and timezone.now() > timezone.datetime.fromisoformat(txn['expires_at']):
                        await self.update_transaction_status(txn['id'], 'EXPIRED')

                        # Send notification
                        await self.create_notification(
                            'Transaction Expired',
                            f"Transaction {txn['reference']} has expired",
                            'transaction_expired',
                            {'transaction_id': txn['id']}
                        )

                        await self.send_transaction_update(txn, 'EXPIRED', "Transaction expired")

                    # Process pending transactions
                    elif txn['status'] in ['PENDING', 'PROCESSING']:
                        # Simulate payment processing with configurable success rate
                        success_rate = await self.get_success_rate()
                        await asyncio.sleep(random.uniform(1, 3))  # Random delay

                        if random.random() < success_rate:
                            # Success
                            await self.update_transaction_status(txn['id'], 'COMPLETED')

                            # Update wallet balance
                            success = await self.update_wallet_balance(txn)

                            if success:
                                # Get updated balance
                                balance = await self.get_user_balance()

                                # Send balance update
                                await self.send_balance_update(balance)

                                # Create balance change record
                                await self.create_balance_change(
                                    txn['transaction_type'],
                                    txn['amount'],
                                    f"{txn['transaction_type'].capitalize()} completed: {txn['reference']}",
                                    txn.get('category', 'GENERAL')
                                )

                                # Create notification
                                await self.create_notification(
                                    'Transaction Completed',
                                    f"{txn['transaction_type'].capitalize()} of {txn['amount']} {txn['currency']} completed",
                                    'transaction_completed',
                                    {'transaction_id': txn['id']}
                                )

                            await self.send_transaction_update(txn, 'COMPLETED', "Transaction completed successfully")

                            # Broadcast to admin if not admin user
                            if not self.user.is_staff:
                                await self.broadcast_to_admin('transaction_completed', {
                                    'user': self.user.username,
                                    'user_id': self.user.id,
                                    'amount': txn['amount'],
                                    'currency': txn['currency'],
                                    'reference': txn['reference'],
                                    'type': txn['transaction_type']
                                })

                        else:
                            # Failure
                            await asyncio.sleep(1)
                            await self.update_transaction_status(txn['id'], 'FAILED')

                            # Create notification
                            await self.create_notification(
                                'Transaction Failed',
                                f"Transaction {txn['reference']} failed",
                                'transaction_failed',
                                {'transaction_id': txn['id']}
                            )

                            await self.send_transaction_update(txn, 'FAILED', "Transaction failed")

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in check_pending_transactions: {e}")
                await asyncio.sleep(30)  # Longer delay on error

    async def check_notifications(self):
        """Periodically check for new notifications"""
        while True:
            try:
                if not self.user.is_authenticated:
                    break

                # Check for new notifications
                new_notifications = await self.get_new_notifications()

                if new_notifications:
                    await self.send(text_data=json.dumps({
                        'type': 'new_notifications',
                        'data': new_notifications,
                        'count': len(new_notifications)
                    }))

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in check_notifications: {e}")
                await asyncio.sleep(60)

    async def send_transaction_update(self, transaction, status, message):
        """Send transaction update to user"""
        transaction['status'] = status
        transaction['updated_at'] = timezone.now().isoformat()

        await self.channel_layer.group_send(
            self.transaction_group_name,
            {
                'type': 'transaction_update',
                'transaction': transaction,
                'status': status,
                'message': message,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def send_balance_update(self, balance):
        """Send balance update to user"""
        await self.channel_layer.group_send(
            self.user_group_name,
            {
                'type': 'balance_update',
                'balance': balance,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def broadcast_to_admin(self, notification_type, data):
        """Broadcast notification to admin panel"""
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'broadcast_notification',
                'notification': {
                    'type': notification_type,
                    'data': data,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )

    async def admin_modify_balance(self, user_id, action, amount, description):
        """Admin modifies user balance with improved validation"""
        try:
            # Validate amount
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    return {'success': False, 'error': 'Amount must be positive'}
            except:
                return {'success': False, 'error': 'Invalid amount format'}

            # Get target user
            target_user = await self.get_user_by_id(user_id)
            if not target_user:
                return {'success': False, 'error': 'User not found'}

            # Get target user's wallet
            wallet = await self.get_user_wallet(target_user)
            old_balance = Decimal(str(wallet['balance']))

            # Calculate new balance
            if action == 'ADD':
                new_balance = old_balance + amount_decimal
            elif action == 'SUBTRACT':
                if amount_decimal > old_balance:
                    return {'success': False, 'error': 'Insufficient balance'}
                new_balance = old_balance - amount_decimal
            elif action == 'SET':
                new_balance = amount_decimal
            elif action == 'BONUS':
                new_balance = old_balance + amount_decimal
            else:
                return {'success': False, 'error': 'Invalid action'}

            # Update wallet
            success = await self.update_wallet_balance_db(target_user['id'], float(new_balance))

            if success:
                # Create balance change record
                change_type = 'BONUS' if action == 'BONUS' else 'ADMIN_MOD'
                await self.create_admin_balance_change(
                    target_user['id'],
                    self.user.id,
                    float(old_balance),
                    float(new_balance),
                    description,
                    change_type
                )

                # Create transaction record
                transaction = await self.create_admin_transaction(
                    target_user['id'],
                    change_type,
                    float(amount_decimal),
                    description,
                    self.user.username
                )

                # Create notification for target user
                await self.create_user_notification(
                    target_user['id'],
                    'Balance Updated',
                    f"Your balance was modified by admin: {description}",
                    'balance_updated',
                    {'admin': self.user.username, 'change': float(amount_decimal)}
                )

                # Send updates to target user
                await self.channel_layer.group_send(
                    f'user_{user_id}',
                    {
                        'type': 'balance_update',
                        'balance': float(new_balance),
                        'reason': description,
                        'admin': self.user.username,
                        'timestamp': timezone.now().isoformat()
                    }
                )

                if transaction:
                    await self.channel_layer.group_send(
                        f'transactions_user_{user_id}',
                        {
                            'type': 'transaction_update',
                            'transaction': transaction,
                            'message': 'Admin modified your balance'
                        }
                    )

                # Broadcast to admin notifications
                await self.broadcast_to_admin('admin_balance_modification', {
                    'admin': self.user.username,
                    'target_user': target_user['username'],
                    'target_user_id': target_user['id'],
                    'old_balance': float(old_balance),
                    'new_balance': float(new_balance),
                    'change': float(amount_decimal),
                    'action': action,
                    'description': description
                })

                return {
                    'success': True,
                    'user_id': user_id,
                    'username': target_user['username'],
                    'old_balance': float(old_balance),
                    'new_balance': float(new_balance),
                    'change': float(new_balance - old_balance),
                    'description': description
                }
            else:
                return {'success': False, 'error': 'Failed to update balance'}

        except Exception as e:
            logger.error(f"Error in admin_modify_balance: {e}")
            return {'success': False, 'error': str(e)}

    async def send_error(self, message, request_id):
        """Send error message"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'request_id': request_id,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))

    # Event handlers for group messages
    async def transaction_update(self, event):
        """Handle transaction updates"""
        await self.send(text_data=json.dumps({
            'type': 'transaction_update',
            'transaction': event.get('transaction'),
            'status': event.get('status'),
            'message': event.get('message'),
            'timestamp': event.get('timestamp')
        }))

    async def balance_update(self, event):
        """Handle balance updates"""
        await self.send(text_data=json.dumps({
            'type': 'balance_update',
            'balance': event.get('balance'),
            'reason': event.get('reason'),
            'admin': event.get('admin'),
            'timestamp': event.get('timestamp')
        }))

    async def broadcast_notification(self, event):
        """Handle broadcast notifications"""
        notification = event.get('notification')

        # Only send admin notifications to staff users
        if notification.get('type') in ['admin_broadcast', 'admin_balance_modification']:
            if self.user.is_staff:
                await self.send(text_data=json.dumps({
                    'type': 'notification',
                    'notification': notification
                }))
        else:
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'notification': notification
            }))

    async def notification_update(self, event):
        """Handle notification updates"""
        await self.send(text_data=json.dumps({
            'type': 'notification_update',
            'notification': event.get('notification')
        }))

    # Database operations
    @database_sync_to_async
    def get_user_transactions(self, limit=50, offset=0, filters=None):
        """Get user's transactions with filtering"""
        from django.db.models import Q

        queryset = Transaction.objects.filter(user=self.user)

        if filters:
            # Apply filters
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            if filters.get('type'):
                queryset = queryset.filter(transaction_type=filters['type'])
            if filters.get('start_date'):
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            if filters.get('end_date'):
                queryset = queryset.filter(created_at__lte=filters['end_date'])
            if filters.get('min_amount'):
                queryset = queryset.filter(amount__gte=filters['min_amount'])
            if filters.get('max_amount'):
                queryset = queryset.filter(amount__lte=filters['max_amount'])
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(reference__icontains=search_term) |
                    Q(description__icontains=search_term) |
                    Q(transaction_id__icontains=search_term)
                )

        total = queryset.count()
        transactions = queryset.order_by('-created_at')[offset:offset + limit]

        return {
            'transactions': [
                {
                    'id': txn.id,
                    'transaction_id': str(txn.transaction_id),
                    'reference': txn.reference,
                    'transaction_type': txn.transaction_type,
                    'category': txn.category.name if txn.category else 'GENERAL',
                    'amount': str(txn.amount),
                    'currency': txn.currency,
                    'status': txn.status,
                    'payment_method': txn.payment_method,
                    'fee_amount': str(txn.fee_amount) if txn.fee_amount else '0.00',
                    'created_at': txn.created_at.isoformat(),
                    'updated_at': txn.updated_at.isoformat() if txn.updated_at else None,
                    'completed_at': txn.completed_at.isoformat() if txn.completed_at else None,
                    'expires_at': txn.expires_at.isoformat() if txn.expires_at else None,
                    'metadata': txn.metadata,
                    'description': txn.description,
                    'balance_before': float(txn.metadata.get('balance_before', 0)) if txn.metadata else None,
                    'balance_after': float(txn.metadata.get('balance_after', 0)) if txn.metadata else None,
                }
                for txn in transactions
            ],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    @database_sync_to_async
    def get_pending_transactions(self):
        """Get user's pending transactions"""
        transactions = Transaction.objects.filter(
            user=self.user,
            status__in=['PENDING', 'PROCESSING']
        )
        return [
            {
                'id': txn.id,
                'transaction_id': str(txn.transaction_id),
                'reference': txn.reference,
                'transaction_type': txn.transaction_type,
                'category': txn.category.name if txn.category else 'GENERAL',
                'amount': float(txn.amount),
                'currency': txn.currency,
                'status': txn.status,
                'expires_at': txn.expires_at.isoformat() if txn.expires_at else None,
            }
            for txn in transactions
        ]

    @database_sync_to_async
    def get_user_balance(self):
        """Get user's wallet balance"""
        try:
            wallet = Wallet.objects.get(user=self.user)
            return float(wallet.balance)
        except Wallet.DoesNotExist:
            # Create wallet if it doesn't exist
            wallet = Wallet.objects.create(user=self.user, balance=0.0)
            return 0.0

    @database_sync_to_async
    def get_balance_history(self, limit=10, offset=0):
        """Get user's balance change history"""
        changes = BalanceChange.objects.filter(user=self.user).order_by('-timestamp')[offset:offset + limit]
        total = BalanceChange.objects.filter(user=self.user).count()

        return {
            'history': [
                {
                    'id': change.id,
                    'old_balance': float(change.old_balance),
                    'new_balance': float(change.new_balance),
                    'change': float(change.change),
                    'description': change.description,
                    'transaction_type': change.transaction_type,
                    'timestamp': change.timestamp.isoformat(),
                    'admin': change.admin.username if change.admin else None
                }
                for change in changes
            ],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    @database_sync_to_async
    def get_users_for_admin(self, limit=50, offset=0, search=''):
        """Get users for admin panel with search"""
        from django.db.models import Q

        queryset = User.objects.all()

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        total = queryset.count()
        users = queryset.order_by('-date_joined')[offset:offset + limit]

        return {
            'users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'date_joined': user.date_joined.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'wallet_balance': float(user.wallet.balance) if hasattr(user, 'wallet') else 0.0
                }
                for user in users
            ],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    @database_sync_to_async
    def get_admin_stats(self):
        """Get admin statistics"""
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Total users
        total_users = User.objects.count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_week = User.objects.filter(date_joined__gte=week_ago).count()

        # Transaction stats
        total_transactions = Transaction.objects.count()
        today_transactions = Transaction.objects.filter(created_at__date=today).count()
        week_transactions = Transaction.objects.filter(created_at__gte=week_ago).count()

        # Revenue stats
        revenue_today = Transaction.objects.filter(
            status='COMPLETED',
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0

        revenue_week = Transaction.objects.filter(
            status='COMPLETED',
            created_at__gte=week_ago
        ).aggregate(total=Sum('amount'))['total'] or 0

        revenue_month = Transaction.objects.filter(
            status='COMPLETED',
            created_at__gte=month_ago
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Pending transactions
        pending_transactions = Transaction.objects.filter(status='PENDING').count()

        return {
            'users': {
                'total': total_users,
                'new_today': new_users_today,
                'new_week': new_users_week
            },
            'transactions': {
                'total': total_transactions,
                'today': today_transactions,
                'week': week_transactions,
                'pending': pending_transactions
            },
            'revenue': {
                'today': float(revenue_today),
                'week': float(revenue_week),
                'month': float(revenue_month)
            }
        }

    @database_sync_to_async
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            user = User.objects.get(id=user_id)
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_wallet(self, user_data):
        """Get user's wallet"""
        try:
            user = User.objects.get(id=user_data['id'])
            wallet = Wallet.objects.get(user=user)
            return {
                'id': wallet.id,
                'balance': float(wallet.balance),
                'currency': wallet.currency
            }
        except (User.DoesNotExist, Wallet.DoesNotExist):
            return {'balance': 0.0, 'currency': 'USD'}

    @database_sync_to_async
    def update_wallet_balance(self, txn_data):
        """Update user's wallet balance after successful transaction"""
        try:
            wallet = Wallet.objects.get(user=self.user)
            old_balance = wallet.balance

            if txn_data['transaction_type'] == 'DEPOSIT':
                wallet.balance += Decimal(str(txn_data['amount']))
            elif txn_data['transaction_type'] == 'WITHDRAWAL':
                wallet.balance -= Decimal(str(txn_data['amount']))

            wallet.save()

            # Update transaction metadata
            txn = Transaction.objects.get(id=txn_data['id'])
            txn.metadata = {
                **(txn.metadata or {}),
                'balance_before': str(old_balance),
                'balance_after': str(wallet.balance)
            }
            txn.save()

            return True
        except Exception as e:
            logger.error(f"Error updating wallet: {e}")
            return False

    @database_sync_to_async
    def update_wallet_balance_db(self, user_id, new_balance):
        """Update wallet balance in database"""
        try:
            user = User.objects.get(id=user_id)
            wallet, created = Wallet.objects.get_or_create(user=user)
            wallet.balance = Decimal(str(new_balance))
            wallet.save()
            return True
        except Exception as e:
            logger.error(f"Error updating wallet balance: {e}")
            return False

    @database_sync_to_async
    def create_balance_change(self, transaction_type, amount, description, category='GENERAL'):
        """Create balance change record"""
        try:
            wallet = Wallet.objects.get(user=self.user)

            # Calculate old balance based on transaction type
            if transaction_type == 'DEPOSIT':
                old_balance = wallet.balance - Decimal(str(amount))
                change = Decimal(str(amount))
            elif transaction_type == 'WITHDRAWAL':
                old_balance = wallet.balance + Decimal(str(amount))
                change = -Decimal(str(amount))
            else:
                old_balance = wallet.balance
                change = Decimal('0')

            BalanceChange.objects.create(
                user=self.user,
                old_balance=old_balance,
                new_balance=wallet.balance,
                change=change,
                description=description,
                transaction_type=transaction_type,
                category=category
            )
            return True
        except Exception as e:
            logger.error(f"Error creating balance change: {e}")
            return False

    @database_sync_to_async
    def create_admin_balance_change(self, user_id, admin_id, old_balance, new_balance, description, transaction_type):
        """Create admin balance change record"""
        try:
            user = User.objects.get(id=user_id)
            admin = User.objects.get(id=admin_id)

            BalanceChange.objects.create(
                user=user,
                admin=admin,
                old_balance=Decimal(str(old_balance)),
                new_balance=Decimal(str(new_balance)),
                change=Decimal(str(new_balance - old_balance)),
                description=description,
                transaction_type=transaction_type
            )
            return True
        except Exception as e:
            logger.error(f"Error creating admin balance change: {e}")
            return False

    @database_sync_to_async
    def create_admin_transaction(self, user_id, transaction_type, amount, description, admin_name):
        """Create admin transaction record"""
        try:
            user = User.objects.get(id=user_id)
            wallet = Wallet.objects.get(user=user)

            transaction = Transaction.objects.create(
                user=user,
                transaction_id=f"ADM{int(timezone.now().timestamp())}{user_id}",
                reference=f"ADMIN-{uuid.uuid4().hex[:8].upper()}",
                transaction_type=transaction_type,
                amount=Decimal(str(amount)),
                currency='USD',
                status='COMPLETED',
                payment_method='ADMIN',
                description=description,
                metadata={
                    'admin': admin_name,
                    'balance_before': str(wallet.balance - Decimal(str(amount))),
                    'balance_after': str(wallet.balance)
                }
            )

            return {
                'id': transaction.id,
                'transaction_id': str(transaction.transaction_id),
                'reference': transaction.reference,
                'transaction_type': transaction.transaction_type,
                'amount': str(transaction.amount),
                'description': transaction.description,
                'created_at': transaction.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error creating admin transaction: {e}")
            return None

    @database_sync_to_async
    def update_transaction_status(self, transaction_id, status):
        """Update transaction status"""
        try:
            txn = Transaction.objects.get(id=transaction_id, user=self.user)
            txn.status = status
            txn.updated_at = timezone.now()

            if status == 'COMPLETED':
                txn.completed_at = timezone.now()

            txn.save()
            return True
        except Transaction.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            return False

    @database_sync_to_async
    def get_transaction_by_id(self, transaction_id):
        """Get transaction by transaction_id"""
        try:
            txn = Transaction.objects.get(transaction_id=transaction_id, user=self.user)
            return {
                'id': txn.id,
                'transaction_id': str(txn.transaction_id),
                'reference': txn.reference,
                'transaction_type': txn.transaction_type,
                'category': txn.category.name if txn.category else 'GENERAL',
                'amount': str(txn.amount),
                'currency': txn.currency,
                'status': txn.status,
                'payment_method': txn.payment_method,
                'description': txn.description,
                'metadata': txn.metadata,
                'created_at': txn.created_at.isoformat(),
                'completed_at': txn.completed_at.isoformat() if txn.completed_at else None
            }
        except Transaction.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting transaction: {e}")
            return None

    @database_sync_to_async
    def get_user_notifications(self, unread_only=False, limit=20):
        """Get user notifications"""
        queryset = Notification.objects.filter(user=self.user)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        notifications = queryset.order_by('-created_at')[:limit]

        return [
            {
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'notification_type': notif.notification_type,
                'data': notif.data,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat(),
                'read_at': notif.read_at.isoformat() if notif.read_at else None
            }
            for notif in notifications
        ]

    @database_sync_to_async
    def get_new_notifications(self):
        """Get new notifications since last check"""
        # Get last checked time (you might want to store this per user)
        # For simplicity, we'll get unread notifications
        notifications = Notification.objects.filter(
            user=self.user,
            is_read=False
        ).order_by('-created_at')[:10]

        return [
            {
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'notification_type': notif.notification_type,
                'created_at': notif.created_at.isoformat()
            }
            for notif in notifications
        ]

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        try:
            notif = Notification.objects.get(id=notification_id, user=self.user)
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save()
            return True
        except Notification.DoesNotExist:
            return False

    @database_sync_to_async
    def create_notification(self, title, message, notification_type, data=None):
        """Create a notification for current user"""
        try:
            Notification.objects.create(
                user=self.user,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data or {}
            )
            return True
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return False

    @database_sync_to_async
    def create_user_notification(self, user_id, title, message, notification_type, data=None):
        """Create a notification for specific user"""
        try:
            user = User.objects.get(id=user_id)
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data or {}
            )
            return True
        except Exception as e:
            logger.error(f"Error creating user notification: {e}")
            return False

    @database_sync_to_async
    def get_transaction_categories(self):
        """Get all transaction categories"""
        categories = TransactionCategory.objects.all()
        return [
            {
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'color': cat.color,
                'icon': cat.icon
            }
            for cat in categories
        ]

    @database_sync_to_async
    def get_success_rate(self):
        """Get transaction success rate (can be configured)"""
        # For demo, return 0.9 (90% success rate)
        # In production, you might want to fetch this from settings or database
        return 0.9

    @database_sync_to_async
    def store_connection_info(self):
        """Store WebSocket connection info"""
        # You might want to store connection info in cache or database
        # For now, just log it
        logger.info(f"Stored connection info for user {self.user_id}")

    @database_sync_to_async
    def remove_connection_info(self):
        """Remove WebSocket connection info"""
        logger.info(f"Removed connection info for user {self.user_id}")

    async def check_transaction_status(self, transaction_id):
        """Check transaction status (placeholder)"""
        return {'status': 'UNKNOWN', 'message': 'Not implemented'}

    async def retry_transaction(self, transaction_id):
        """Retry a failed transaction (placeholder)"""
        return {'success': False, 'message': 'Not implemented'}

    async def admin_create_transaction(self, user_id, transaction_data):
        """Admin creates a transaction for user (placeholder)"""
        return {'success': False, 'message': 'Not implemented'}


class AdminBroadcastConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for admin broadcast notifications"""

    async def connect(self):
        self.user = self.scope["user"]
        self.user_id = str(self.user.id) if self.user.is_authenticated else None

        logger.info(f"Admin broadcast connection attempt for user: {self.user}")

        if self.user.is_authenticated and self.user.is_staff:
            try:
                await self.channel_layer.group_add(
                    'admin_notifications',
                    self.channel_name
                )

                await self.channel_layer.group_add(
                    'admin_control',
                    self.channel_name
                )

                await self.accept()

                logger.info(f"Admin broadcast connected: {self.user.username}")

            except Exception as e:
                logger.error(f"Error in admin broadcast connect: {e}")
                await self.close(code=4000)
        else:
            await self.close(code=4001)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'admin_notifications',
            self.channel_name
        )

        await self.channel_layer.group_discard(
            'admin_control',
            self.channel_name
        )

        logger.info(f"Admin broadcast disconnected: {self.user.username}")

    async def receive(self, text_data):
        """Handle admin broadcast messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            request_id = data.get('request_id', str(uuid.uuid4()))

            if message_type == 'broadcast_message' and self.user.is_staff:
                message = data.get('message')
                notification_type = data.get('notification_type', 'info')
                target_group = data.get('target_group', 'all_users')  # all_users, specific_users, admins

                if target_group == 'all_users':
                    # Broadcast to all users via a different mechanism
                    # You might want to store this in database and let each user's consumer check
                    pass
                elif target_group == 'admins':
                    # Broadcast to admin group
                    await self.channel_layer.group_send(
                        'admin_notifications',
                        {
                            'type': 'broadcast_notification',
                            'notification': {
                                'type': 'admin_broadcast',
                                'message': message,
                                'admin': self.user.username,
                                'notification_type': notification_type,
                                'timestamp': timezone.now().isoformat()
                            }
                        }
                    )

                    await self.send(text_data=json.dumps({
                        'type': 'response',
                        'request_id': request_id,
                        'success': True,
                        'message': 'Broadcast sent to admins'
                    }))

            elif message_type == 'admin_command' and self.user.is_staff:
                command = data.get('command')
                params = data.get('params', {})

                # Handle admin commands
                if command == 'refresh_cache':
                    # Refresh cache command
                    await self.handle_refresh_cache(params)

                elif command == 'system_status':
                    # Get system status
                    status = await self.get_system_status()
                    await self.send(text_data=json.dumps({
                        'type': 'response',
                        'request_id': request_id,
                        'success': True,
                        'data': status
                    }))

                else:
                    await self.send(text_data=json.dumps({
                        'type': 'response',
                        'request_id': request_id,
                        'success': False,
                        'error': f'Unknown command: {command}'
                    }))

        except Exception as e:
            logger.error(f"Error in admin broadcast receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'request_id': data.get('request_id', 'unknown'),
                'message': str(e)
            }))

    async def broadcast_notification(self, event):
        """Handle broadcast notifications"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event.get('notification')
        }))

    @database_sync_to_async
    def get_system_status(self):
        """Get system status for admin"""
        from django.db import connection
        from django.core.cache import cache

        # Check database
        db_ok = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_ok = True
        except:
            db_ok = False

        # Check cache
        cache_ok = False
        try:
            cache.set('test_key', 'test_value', 1)
            cache_ok = cache.get('test_key') == 'test_value'
        except:
            cache_ok = False

        # Get active connections (simplified)
        # In production, you might want to use a more sophisticated method

        return {
            'database': db_ok,
            'cache': cache_ok,
            'timestamp': timezone.now().isoformat()
        }

    async def handle_refresh_cache(self, params):
        """Handle cache refresh command"""
        # Implement cache refresh logic
        pass


# Utility functions to send updates from Django views
def send_balance_update(user_id, new_balance, reason=None, admin=None):
    """Send balance update via WebSocket (call from Django views)"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'balance_update',
            'balance': float(new_balance),
            'reason': reason,
            'admin': admin,
            'timestamp': timezone.now().isoformat()
        }
    )


def send_transaction_update(user_id, transaction_data):
    """Send transaction update via WebSocket (call from Django views)"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f'transactions_user_{user_id}',
        {
            'type': 'transaction_update',
            'transaction': transaction_data,
            'message': 'New transaction added',
            'timestamp': timezone.now().isoformat()
        }
    )


def send_notification(user_id, title, message, notification_type='info', data=None):
    """Send notification via WebSocket (call from Django views)"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from django.contrib.auth.models import User
    from .models import Notification

    channel_layer = get_channel_layer()

    # Create notification in database
    try:
        user = User.objects.get(id=user_id)
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data or {}
        )

        # Send via WebSocket
        async_to_sync(channel_layer.group_send)(
            f'notifications_user_{user_id}',
            {
                'type': 'notification_update',
                'notification': {
                    'id': notification.id,
                    'title': title,
                    'message': message,
                    'notification_type': notification_type,
                    'data': data or {},
                    'created_at': notification.created_at.isoformat()
                }
            }
        )

        return True
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False


def broadcast_admin_notification(notification_type, data):
    """Broadcast notification to all admin users"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        'admin_notifications',
        {
            'type': 'broadcast_notification',
            'notification': {
                'type': notification_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
        }
    )

class BroadcastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join broadcast group
        await self.channel_layer.group_add(
            'broadcast',
            self.channel_name
        )

        # Check if user is admin/staff
        user = self.scope['user']
        if user.is_staff or user.is_superuser:
            await self.channel_layer.group_add(
                'admin_broadcast',
                self.channel_name
            )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave broadcast group
        await self.channel_layer.group_discard(
            'broadcast',
            self.channel_name
        )

        user = self.scope['user']
        if user.is_staff or user.is_superuser:
            await self.channel_layer.group_discard(
                'admin_broadcast',
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'broadcast')

        if message_type == 'broadcast':
            user = self.scope['user']

            # Only allow staff/superusers to send broadcasts
            if not (user.is_staff or user.is_superuser):
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Unauthorized: Only administrators can send broadcasts'
                }))
                return

            title = data['title']
            message = data['message']
            priority = data.get('priority', 'normal')
            broadcast_type = data.get('broadcast_type', 'announcement')

            # Save broadcast to database
            await self.save_broadcast_message(
                user.id,
                title,
                message,
                priority,
                broadcast_type
            )

            # Send to all users
            await self.channel_layer.group_send(
                'broadcast',
                {
                    'type': 'broadcast_message',
                    'title': title,
                    'message': message,
                    'sender': user.username,
                    'priority': priority,
                    'broadcast_type': broadcast_type,
                    'timestamp': data.get('timestamp')
                }
            )

    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'broadcast',
            'title': event['title'],
            'message': event['message'],
            'sender': event['sender'],
            'priority': event['priority'],
            'broadcast_type': event['broadcast_type'],
            'timestamp': event.get('timestamp')
        }))

    @database_sync_to_async
    def save_broadcast_message(self, sender_id, title, message, priority, broadcast_type):
        BroadcastMessage.objects.create(
            sender_id=sender_id,
            title=title,
            message=message,
            priority=priority,
            broadcast_type=broadcast_type
        )


import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import uuid

from your_app.models import User, ChatMessage, ChatRoom, UserStatus, ChatRoomMember, Notification


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        if self.user == AnonymousUser():
            await self.close()
            return

        # Join user's personal room
        self.user_room = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_room,
            self.channel_name
        )

        # Update user status
        await self.update_user_status(True)

        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to chat',
            'user_id': self.user.id
        }))

    async def disconnect(self, close_code):
        if self.user != AnonymousUser():
            # Leave user's personal room
            await self.channel_layer.group_discard(
                self.user_room,
                self.channel_name
            )

            # Update user status
            await self.update_user_status(False)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'stop_typing':
                await self.handle_stop_typing(data)
            elif message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'message_read':
                await self.handle_message_read(data)
            elif message_type == 'message_delivered':
                await self.handle_message_delivered(data)
            elif message_type == 'reaction':
                await self.handle_reaction(data)

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_message(self, data):
        """Handle incoming message"""
        receiver_id = data.get('receiver_id')
        content = data.get('content')
        message_type = data.get('message_type', 'text')
        reply_to = data.get('reply_to')
        ws_message_id = data.get('ws_message_id', f"ws_{uuid.uuid4().hex[:16]}")

        if not receiver_id or not content:
            return

        # Save message to database
        message = await self.save_message(
            receiver_id, content, message_type, reply_to, ws_message_id
        )

        if message:
            # Get receiver's room
            receiver_room = f"user_{receiver_id}"

            # Send to receiver
            await self.channel_layer.group_send(
                receiver_room,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id
                }
            )

            # Send confirmation to sender
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'ws_message_id': ws_message_id,
                'db_message_id': str(message['id']),
                'timestamp': message['timestamp']
            }))

    async def handle_typing(self, data):
        """Handle typing indicator"""
        receiver_id = data.get('receiver_id')

        if not receiver_id:
            return

        # Update typing status in database
        await self.update_typing_status(receiver_id, True)

        # Notify receiver
        receiver_room = f"user_{receiver_id}"
        await self.channel_layer.group_send(
            receiver_room,
            {
                'type': 'user_typing',
                'sender_id': self.user.id,
                'sender_name': self.user.username,
                'is_typing': True
            }
        )

    async def handle_stop_typing(self, data):
        """Handle stop typing indicator"""
        receiver_id = data.get('receiver_id')

        if not receiver_id:
            return

        # Update typing status in database
        await self.update_typing_status(receiver_id, False)

        # Notify receiver
        receiver_room = f"user_{receiver_id}"
        await self.channel_layer.group_send(
            receiver_room,
            {
                'type': 'user_typing',
                'sender_id': self.user.id,
                'sender_name': self.user.username,
                'is_typing': False
            }
        )

    async def handle_message_read(self, data):
        """Handle message read receipt"""
        message_ids = data.get('message_ids', [])
        room_id = data.get('room_id')

        if message_ids:
            await self.mark_messages_as_read(message_ids)

            # Notify sender that messages were read
            for message_id in message_ids:
                message = await self.get_message(message_id)
                if message and message['sender']['id'] != self.user.id:
                    sender_room = f"user_{message['sender']['id']}"
                    await self.channel_layer.group_send(
                        sender_room,
                        {
                            'type': 'message_read',
                            'message_id': message_id,
                            'reader_id': self.user.id
                        }
                    )

    async def handle_message_delivered(self, data):
        """Handle message delivered receipt"""
        message_id = data.get('message_id')

        if message_id:
            await self.mark_message_as_delivered(message_id)

            # Notify sender
            message = await self.get_message(message_id)
            if message and message['sender']['id'] != self.user.id:
                sender_room = f"user_{message['sender']['id']}"
                await self.channel_layer.group_send(
                    sender_room,
                    {
                        'type': 'message_delivered',
                        'message_id': message_id,
                        'receiver_id': self.user.id
                    }
                )

    async def handle_reaction(self, data):
        """Handle message reaction"""
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        action = data.get('action', 'add')  # 'add' or 'remove'

        if not message_id or not emoji:
            return

        # Update reaction in database
        message = await self.update_reaction(message_id, emoji, action)

        if message:
            # Notify both sender and receiver
            sender_room = f"user_{message['sender']['id']}"
            receiver_room = f"user_{message['receiver']['id']}"

            reaction_event = {
                'type': 'message_reaction',
                'message_id': message_id,
                'emoji': emoji,
                'action': action,
                'user_id': self.user.id
            }

            # Send to sender if they're not the one reacting
            if message['sender']['id'] != self.user.id:
                await self.channel_layer.group_send(sender_room, reaction_event)

            # Send to receiver if they're not the one reacting
            if message['receiver']['id'] != self.user.id:
                await self.channel_layer.group_send(receiver_room, reaction_event)

    # Database operations
    @database_sync_to_async
    def save_message(self, receiver_id, content, message_type, reply_to, ws_message_id):
        """Save message to database"""
        try:
            from django.shortcuts import get_object_or_404

            receiver = get_object_or_404(User, id=receiver_id)
            chat_room = ChatRoom.get_or_create_direct_chat(self.user, receiver)

            # Get replied message if exists
            reply_to_message = None
            if reply_to:
                reply_to_message = ChatMessage.objects.filter(
                    ws_message_id=reply_to,
                    chat_room=chat_room
                ).first()

            # Create message
            message = ChatMessage.objects.create(
                sender=self.user,
                receiver=receiver,
                chat_room=chat_room,
                content=content,
                message_type=message_type,
                reply_to=reply_to_message,
                ws_message_id=ws_message_id,
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
                title='New Message',
                message=f"New message from {self.user.profile.get_display_name()}",
                related_user=self.user
            )

            return message.to_dict()

        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def update_user_status(self, is_online):
        """Update user's online status"""
        user_status, created = UserStatus.objects.get_or_create(user=self.user)
        user_status.update_online_status(is_online)
        return user_status

    @database_sync_to_async
    def update_typing_status(self, receiver_id, is_typing):
        """Update user's typing status"""
        user_status, created = UserStatus.objects.get_or_create(user=self.user)

        if is_typing:
            from django.shortcuts import get_object_or_404
            receiver = get_object_or_404(User, id=receiver_id)
            chat_room = ChatRoom.get_or_create_direct_chat(self.user, receiver)
            user_status.update_typing_status(typing_to=receiver, typing_room=chat_room)
        else:
            user_status.clear_typing_status()

        return user_status

    @database_sync_to_async
    def mark_messages_as_read(self, message_ids):
        """Mark messages as read"""
        messages = ChatMessage.objects.filter(
            id__in=message_ids,
            receiver=self.user,
            is_read=False
        )

        for message in messages:
            message.mark_as_read()

        return messages.count()

    @database_sync_to_async
    def mark_message_as_delivered(self, message_id):
        """Mark message as delivered"""
        try:
            message = ChatMessage.objects.get(id=message_id, receiver=self.user)
            return message.mark_as_delivered()
        except ChatMessage.DoesNotExist:
            return False

    @database_sync_to_async
    def get_message(self, message_id):
        """Get message by ID"""
        try:
            message = ChatMessage.objects.get(id=message_id)
            return message.to_dict()
        except ChatMessage.DoesNotExist:
            return None

    @database_sync_to_async
    def update_reaction(self, message_id, emoji, action):
        """Update message reaction"""
        try:
            message = ChatMessage.objects.get(id=message_id)

            if action == 'add':
                message.add_reaction(self.user, emoji)
            else:
                message.remove_reaction(self.user, emoji)

            return message.to_dict()
        except ChatMessage.DoesNotExist:
            return None

    # Event handlers for group messages
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender_id': event['sender_id']
        }))

    async def user_typing(self, event):
        """Send typing indicator to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'is_typing': event['is_typing']
        }))

    async def message_read(self, event):
        """Send message read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_read',
            'message_id': event['message_id'],
            'reader_id': event['reader_id']
        }))

    async def message_delivered(self, event):
        """Send message delivered receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_delivered',
            'message_id': event['message_id'],
            'receiver_id': event['receiver_id']
        }))

    async def message_reaction(self, event):
        """Send message reaction to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'message_id': event['message_id'],
            'emoji': event['emoji'],
            'action': event['action'],
            'user_id': event['user_id']
        }))

    async def user_status_update(self, event):
        """Send user status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'is_online': event['is_online'],
            'last_seen': event['last_seen']
        }))


# community/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import UserStatus
from asgiref.sync import sync_to_async


class SearchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f'search_{self.user.username}'
        self.online_group_name = 'search_online'

        # Join room groups
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.channel_layer.group_add(
            self.online_group_name,
            self.channel_name
        )

        await self.accept()

        # Update user online status
        await self.update_user_status(True)

        # Send online count
        online_count = await self.get_online_count()
        await self.send(text_data=json.dumps({
            'type': 'online_count',
            'count': online_count
        }))

        # Notify others
        await self.channel_layer.group_send(
            self.online_group_name,
            {
                'type': 'user_online',
                'user': self.user.username
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user.is_authenticated:
            # Update user offline status
            await self.update_user_status(False)

            # Leave room groups
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            await self.channel_layer.group_discard(
                self.online_group_name,
                self.channel_name
            )

            # Notify others
            await self.channel_layer.group_send(
                self.online_group_name,
                {
                    'type': 'user_offline',
                    'user': self.user.username
                }
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'typing':
            await self.handle_typing(data)
        elif message_type == 'get_online_count':
            online_count = await self.get_online_count()
            await self.send(text_data=json.dumps({
                'type': 'online_count',
                'count': online_count
            }))

    async def handle_typing(self, data):
        user_id = data.get('user_id')
        await self.channel_layer.group_send(
            f'search_user_{user_id}',
            {
                'type': 'typing',
                'user_id': self.user.id
            }
        )

    async def user_online(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_online',
            'user': event['user']
        }))

    async def user_offline(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_offline',
            'user': event['user']
        }))

    async def typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id']
        }))

    @database_sync_to_async
    def update_user_status(self, is_online):
        status, created = UserStatus.objects.get_or_create(user=self.user)
        status.is_online = is_online
        status.save()

    @database_sync_to_async
    def get_online_count(self):
        return UserStatus.objects.filter(is_online=True).count()