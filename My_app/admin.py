# admin.py - Fixed version WITHOUT importing views
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.urls import path
from .models import (
    Profile, KYCApplication, Wallet, Transaction, BalanceChange,
    SocialPost, SocialPostLike, SocialComment, FollowRelationship,
    Report, Notification, Subscriber, ChatMessage, BroadcastMessage,
    ChatRoom, ChatRoomMember
)

# Remove the redundant import
# from .models import ChatRoom, ChatRoomMember  # This line is duplicate, remove it

# Register your models here
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'kyc_verified', 'created_at']
    search_fields = ['user__username', 'user__email', 'community_username']
    list_filter = ['plan', 'kyc_verified', 'is_private']

@admin.register(KYCApplication)
class KYCApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'status', 'submitted_at']
    list_filter = ['status', 'document_type']
    search_fields = ['user__username', 'full_name', 'document_number']

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'currency', 'is_active']
    search_fields = ['user__username']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'txn_type', 'amount', 'status', 'created_at']
    list_filter = ['txn_type', 'status', 'payment_method']
    search_fields = ['reference', 'user__username', 'transaction_id']

@admin.register(BalanceChange)
class BalanceChangeAdmin(admin.ModelAdmin):
    list_display = ['user', 'change', 'transaction_type', 'timestamp']
    list_filter = ['transaction_type']
    search_fields = ['user__username']

@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ['author', 'post_type', 'trading_symbol', 'likes_count', 'created_at']
    list_filter = ['post_type', 'visibility', 'is_active']
    search_fields = ['author__username', 'content', 'trading_symbol']

@admin.register(SocialPostLike)
class SocialPostLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'reaction_type', 'created_at']

@admin.register(SocialComment)
class SocialCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'created_at', 'is_active']

@admin.register(FollowRelationship)
class FollowRelationshipAdmin(admin.ModelAdmin):
    list_display = ['follower', 'followed', 'created_at']

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['reporter', 'report_type', 'status', 'created_at']
    list_filter = ['report_type', 'status']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']

@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'is_active', 'is_verified', 'subscribed_at']
    list_filter = ['is_active', 'is_verified', 'source']

# Remove the custom dashboard section if it's causing issues
# Or comment it out for now
# class MyModelAdmin(admin.ModelAdmin):
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path('dashboard/', self.admin_site.admin_view(views.admin_dashboard), name='admin_dashboard'),
#         ]
#         return custom_urls + urls
#
#     def get_model_perms(self, request):
#         # Ensure this appears in admin
#         return super().get_model_perms(request)

# No need to re-import models that are already imported
# Remove these lines:
# from .models import ChatMessage, BroadcastMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'message_type', 'is_read', 'created_at']
    list_filter = ['message_type', 'is_read', 'created_at']
    search_fields = ['sender__username', 'receiver__username', 'content']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ['title', 'broadcast_type', 'is_published', 'sent_count', 'read_count', 'created_at']
    list_filter = ['broadcast_type', 'is_published', 'target_audience']
    search_fields = ['title', 'content']
    readonly_fields = ['sent_count', 'read_count', 'click_count', 'created_at', 'updated_at']
    actions = ['publish_selected', 'unpublish_selected']

    def publish_selected(self, request, queryset):
        queryset.update(is_published=True, published_at=timezone.now())
        self.message_user(request, f"{queryset.count()} broadcasts published.")

    publish_selected.short_description = "Publish selected broadcasts"

    def unpublish_selected(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, f"{queryset.count()} broadcasts unpublished.")

    unpublish_selected.short_description = "Unpublish selected broadcasts"

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_type', 'creator', 'member_count', 'message_count', 'is_active', 'created_at']
    list_filter = ['room_type', 'is_active', 'is_public', 'is_archived']
    search_fields = ['name', 'description', 'creator__username']
    # Remove filter_horizontal for 'members' since it uses through model
    filter_horizontal = ['admins']  # Only admins can be in filter_horizontal
    readonly_fields = ['member_count', 'message_count', 'last_activity', 'created_at', 'updated_at']

    # Add a custom method to display members
    def get_members_display(self, obj):
        return ", ".join([member.username for member in obj.members.all()[:5]])

    get_members_display.short_description = "Members"

@admin.register(ChatRoomMember)
class ChatRoomMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'chat_room', 'role', 'is_muted', 'joined_at', 'unread_count']
    list_filter = ['role', 'is_muted', 'chat_room__room_type']
    search_fields = ['user__username', 'chat_room__name', 'nickname']
    readonly_fields = ['joined_at', 'last_seen', 'last_read']