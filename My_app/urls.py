# My_app/urls.py
from django.urls import path, re_path
from . import views
from . import admin_views
from django.contrib.auth import views as auth_views

from .views import advanced_search

urlpatterns = [
    # Basic pages
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('user/', views.user, name='user'),

    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registration-success/', views.registration_success_view, name='registration_success'),
    path('check-username/', views.check_username, name='check_username'),

    # Admin
    path('admin/login/', views.admin_login_view, name='admin_login'),

    # Profile & Settings
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('base/', views.base_view, name='base'),

    # Trading Pages
    path('strategy-lab/', views.strategy_lab, name='strategy_lab'),
    path('advanced-trading-tools/', views.advanced_trading_tools, name='advanced_trading_tools'),
    path('algo-trading-platform/', views.algo_trading_platform, name='algo_trading_platform'),
    path('trade-builder/', views.trade_builder, name='trade_builder'),
    path('market-blueprint/', views.market_blueprint, name='market_blueprint'),
    path('charting-suite/', views.charting_suite, name='charting_suite'),
    path('indicator-workshop/', views.indicator_workshop, name='indicator_workshop'),
    path('trading-toolkit/', views.trading_toolkit, name='trading_toolkit'),
    path('backtest-center/', views.backtest_center, name='backtest_center'),
    path('trade-development/', views.trade_development, name='trade_development'),
    path('market-research/', views.market_research, name='market_research'),
    path('execution-hub/', views.execution_hub, name='execution_hub'),
    path('live-trading/', views.live_trading, name='live_trading'),
    path('trade-operations/', views.trade_operations, name='trade_operations'),
    path('market-monitor/', views.market_monitor, name='market_monitor'),
    path('sentiment-watch/', views.sentiment_watch, name='sentiment_watch'),
    path('automation-center/', views.automation_center, name='automation_center'),
    path('risk-console/', views.risk_console, name='risk_console'),
    path('performance-tracker/', views.performance_tracker, name='performance_tracker'),
    path('signal-runner/', views.signal_runner, name='signal_runner'),
    path('trade-manager/', views.trade_manager, name='trade_manager'),
    path('position-control/', views.position_control, name='position_control'),
    path('trading-platform/', views.trading_platform, name='trading_platform'),

    # KYC & Transactions
    path('kyc/', views.kyc_apply, name='kyc'),
    path('deposit/', views.deposit, name='deposit'),
    path('withdraw/', views.withdraw, name='withdraw'),
    path('transactions/', views.transactions, name='transactions'),
    path('transaction-history/', views.transaction_history, name='transaction_history'),
    path('transaction/<str:transaction_id>/', views.transaction_status, name='transaction_status'),

    # Payment Processing
    path('process-deposit/', views.deposit_funds, name='process_deposit'),
    path('process-withdrawal/', views.withdraw_funds, name='process_withdrawal'),
    path('deposit-funds/', views.deposit_funds, name='deposit_funds'),

    # API Endpoints
    path('api/live-transactions/', views.live_transactions, name='api_live_transactions'),
    path('api/transactions/', views.api_transactions_list, name='api_transactions'),
    path('api/transaction/<str:transaction_id>/', views.api_transaction_details, name='api_transaction_details'),
    path('api/transaction/<str:transaction_id>/retry/', views.api_retry_transaction, name='api_retry_transaction'),
    path('api/transaction/<str:transaction_id>/status/', views.transaction_status_api, name='transaction_status_api'),
    path('api/transaction/<str:transaction_id>/refund/', views.transaction_refund_api, name='transaction_refund_api'),
    path('api/transactions/stats/', views.transaction_stats_api, name='transaction_stats_api'),
    path('api/transactions/export/', views.export_transactions_api, name='export_transactions'),
    path('api/wallet/balance/', views.wallet_balance, name='wallet_balance'),
    path('api/check-transaction/<str:transaction_id>/', views.check_transaction_status,
         name='check_transaction_status'),

    # AJAX endpoints
    path('ajax/deposit/', views.ajax_deposit, name='ajax_deposit'),
    path('ajax/withdraw/', views.ajax_withdraw, name='ajax_withdraw'),
    path('create-transaction/', views.create_transaction, name='create_transaction'),

    # Webhook endpoints
    path('webhook/mpesa/', views.mpesa_callback, name='mpesa_callback'),
    path('webhook/paypal/', views.webhook_paypal, name='paypal_webhook'),
    path('webhook/stripe/', views.webhook_stripe, name='stripe_webhook'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),

    # Admin API
    path('admin/modify-balance/', views.admin_modify_balance, name='admin_modify_balance'),
    path('admin/kyc/', views.kyc_admin_panel, name='kyc_admin'),
    path('admin/kyc/<int:kyc_id>/approve/', views.approve_kyc, name='approve_kyc'),

    # Market Data
    path('api/price/<str:symbol>/', views.get_price, name='get_price'),
    path('api/realtime-price/<str:symbol>/', views.get_realtime_price, name='realtime_price'),

    # Stripe
    path('create-stripe-session/', views.create_stripe_session, name='create_stripe_session'),
    path('billing/', views.billing_view, name='billing'),

    # Social Login
    path('auth/google/', views.google_login, name='google_login'),
    path('auth/google/callback/', views.google_callback, name='google_callback'),
    path('auth/facebook/', views.facebook_login, name='facebook_login'),
    path('auth/facebook/callback/', views.facebook_callback, name='facebook_callback'),
    path('auth/telegram/', views.telegram_login, name='telegram_login'),
    path('auth/telegram/callback/', views.telegram_callback, name='telegram_callback'),
    path('auth/instagram/', views.instagram_login, name='instagram_login'),
    path('auth/instagram/callback/', views.instagram_callback, name='instagram_callback'),

    # Messaging System
    path('messages/', views.user_messages, name='messages'),
    path('messages/compose/', views.compose_message, name='compose_message'),
    path('messages/<int:message_id>/', views.view_message, name='view_message'),
    path('messages/<int:message_id>/reply/', views.reply_message, name='reply_message'),
    path('messages/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('messages/<int:message_id>/mark-read/', views.mark_message_read, name='mark_message_read'),

    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/notifications/counts/', views.api_notification_counts, name='api_notification_counts'),
    path('notifications/<str:notification_id>/edit/', views.edit_notification, name='edit_notification'),
    path('notifications/<str:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    path('notifications/<str:notification_id>/toggle/', views.toggle_notification_status, name='toggle_notification'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),

    # Legal pages
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('contact1/', views.contact1, name='contact1'),
    path('risk-disclosure/', views.risk_disclosure, name='risk_disclosure'),

    # Other
    path('subscribe/', views.subscribe_view, name='subscribe'),
    path('new-year/', views.new_year_view, name='new_year'),
    path('home-redirect/', views.home_redirect, name='home_redirect'),

    # Redirects and aliases
    path('', views.home_redirect, name='home'),

    path('send-message/', views.send_message, name='send_message'),
    path('send-broadcast/', views.send_broadcast, name='send_broadcast'),
    path('get-recent-messages/', views.get_recent_messages, name='get_recent_messages'),

    path('deposit/', views.deposit, name='deposit'),
    path('deposit/process/', views.process_deposit, name='process_deposit'),

    # Transaction URLs
    path('transactions/', views.transactions, name='transactions'),
    path('transaction/<str:transaction_id>/status/', views.transaction_status, name='transaction_status'),
    path('transaction/<str:transaction_id>/retry/', views.retry_transaction, name='retry_transaction'),

    # API Endpoints
    path('api/transactions/live/', views.api_live_transactions, name='api_live_transactions'),
    path('api/transactions/<str:transaction_id>/details/', views.api_transaction_details,
         name='api_transaction_details'),
    path('api/transactions/<str:transaction_id>/retry/', views.api_retry_transaction, name='api_retry_transaction'),
    path('api/transactions/list/', views.api_transactions_list, name='api_transactions_list'),

    # Payment Callbacks
    path('callback/mpesa/', views.mpesa_callback, name='mpesa_callback'),
    path('callback/paypal/success/', views.paypal_success, name='paypal_success'),
    path('callback/paypal/cancel/', views.paypal_cancel, name='paypal_cancel'),
    path('callback/alipay/', views.alipay_callback, name='alipay_callback'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),

    # Utility URLs
    path('api/wallet/balance/', views.wallet_balance, name='wallet_balance'),
    path('api/verify-payment/', views.verify_payment, name='verify_payment'),

    # Legacy URLs (for compatibility)
    path('deposit/funds/', views.deposit_funds, name='deposit_funds'),
    path('transaction/history/', views.transaction_history, name='transaction_history'),

    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/transactions/', admin_views.admin_transactions, name='admin_transactions'),
    path('admin/transactions/<uuid:transaction_id>/', admin_views.admin_transaction_detail,
         name='admin_transaction_detail'),
    path('admin/users/', admin_views.admin_users, name='admin_users'),
    path('admin/users/<int:user_id>/', admin_views.admin_user_detail, name='admin_user_detail'),
    path('admin/kyc/', admin_views.admin_kyc, name='admin_kyc'),
    path('admin/kyc/<int:kyc_id>/', admin_views.admin_kyc_detail, name='admin_kyc_detail'),
    path('admin/export/transactions/', admin_views.export_transactions_csv, name='export_transactions_csv'),
    path('admin/api/stats/', admin_views.api_transaction_stats, name='api_transaction_stats'),

    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('accounts/login/', views.custom_login_view, name='login'),
    path('accounts/logout/',
         auth_views.LogoutView.as_view(next_page='login'),
         name='logout'),
    #new paths
    # Community/Interaction URLs
    path('community/', views.community_feed, name='community_feed'),
    path('community/post/create/', views.create_post, name='create_post'),
    path('community/post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('community/post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('community/post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('community/post/<int:post_id>/like/', views.toggle_like, name='toggle_like'),
    path('community/post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('community/comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # User profiles
    path('community/profile/<str:username>/', views.user_profile, name='user_profile'),
    path('community/profile/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('community/following/', views.following_list, name='following_list'),
    path('community/followers/', views.followers_list, name='followers_list'),
    path('community/message-list/', views.messages_list, name='message_list'),

    # Chat/Message URLs
    # Update these URLs in your urls.py:
    path('community/messages/', views.chat_list_view, name='chat_list'),  # Changed from chat_detail
    path('community/create-group/', views.create_group_chat, name='create_group_chat'),
    path('community/messages/<str:username>/', views.chat_detail, name='chat_detail'),
    # Make sure this uses chat_detail
    path('community/messages/group/<int:room_id>/', views.group_chat, name='group_chat'),
    # path('community/messages/create-group/', views.create_group_chat, name='create_group_chat'),

    # Search
    path('community/search/', views.search_users, name='search_users'),

    # Notifications
    path('community/notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # API endpoints for AJAX
    path('api/like-post/', views.api_like_post, name='api_like_post'),
    path('api/add-comment/', views.api_add_comment, name='api_add_comment'),
    path('api/follow-user/', views.api_follow_user, name='api_follow_user'),
    path('api/send-message/', views.api_send_message, name='api_send_message'),
    path('api/get-messages/', views.api_get_messages, name='api_get_messages'),
    path('api/delete-post/', views.api_delete_post, name='api_delete_post'),

    path('community/search/', views.search_users, name='search'),

    # Posts
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),

    # Comments
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    # path('comment/<int:comment_id>/reply/', views.add_reply, name='add_reply'),
    # path('comment/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
    # path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # Interactions
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/save/', views.save_post, name='save_post'),
    # path('post/<int:post_id>/share/', views.share_post, name='share_post'),

    # Notifications
    path('community/notifications/', views.notifications1, name='notifications1'),
    path('follow/', views.api_follow_user, name='api_follow_user'),

    # Post interactions
    path('post/like/', views.api_like_post, name='api_like_post'),
    # path('post/save/', views.api_save_post, name='api_save_post'),
    path('post/comment/', views.api_add_comment, name='api_add_comment'),

    # path('community/messages/api', views.messages_list, name='messages'),
    path('messages/<str:username>/', views.messages_conversation, name='messages_conversation'),
    path('api/send-message/', views.api_send_message, name='api_send_message'),
    path('api/get-messages/<str:username>/', views.api_get_messages, name='api_get_messages'),

    # Profile URLs
    path('profile/<str:username>/', views.user_profile, name='user_profile'),
    path('search/', views.advanced_search, name='search_users'),
    path('api/follow/', views.api_follow_user, name='api_follow_user'),
    path('api/search/suggestions/', views.api_search_suggestions, name='api_search_suggestions'),
    path('api/message/<str:username>/', views.api_message_user, name='api_message_user'),

    # API URLs for follow/unfollow
    path('api/follow/', views.api_follow_user, name='api_follow_user'),
    # Add these to your urlpatterns:
    path('api/chat-list/', views.api_chat_list, name='api_chat_list'),
    path('api/get-messages/<str:username>/', views.api_get_messages, name='api_get_messages'),
    path('api/send-message/', views.api_send_message, name='api_send_message'),

    # Chat API endpoints
    path('api/get-messages/<str:username>/', views.get_messages, name='get_messages'),
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/upload-chat-file/', views.upload_chat_file, name='upload_chat_file'),
    path('api/update-user-status/', views.update_user_status, name='update_user_status'),
    path('api/get-user-status/<str:username>/', views.get_user_status, name='get_user_status'),
    path('api/update-typing-status/', views.update_typing_status, name='update_typing_status'),
    path('api/get-chat-list/', views.get_chat_list, name='get_chat_list'),
    path('api/mark-messages-as-read/', views.mark_messages_as_read, name='mark_messages_as_read'),
    path('api/delete-message/', views.delete_message, name='delete_message'),
    path('api/react-to-message/', views.react_to_message, name='react_to_message'),
    path('api/create-chat-room/', views.create_chat_room, name='create_chat_room'),

    path('social/post/<int:pk>/', views.social_post_detail, name='social_post_detail'),
    path('posts/by-tag/<str:tag>/', views.posts_by_tag, name='posts_by_tag'),

    # Bio and profile settings APIs
    path('api/update-bio/', views.api_update_bio, name='api_update_bio'),
    path('api/update-profile-settings/', views.api_update_profile_settings, name='api_update_profile_settings'),
]