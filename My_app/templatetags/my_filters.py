# My_app/templatetags/my_filters.py
from django import template
from django.contrib.auth.models import User

register = template.Library()


# Follow-related filters
@register.filter
def is_followed_by(user, current_user):
    """Check if current_user follows user."""
    if not current_user or not user:
        return False
    if not isinstance(current_user, User):
        return False
    if not current_user.is_authenticated:
        return False

    try:
        from ..models import FollowRelationship
        return FollowRelationship.objects.filter(
            follower=current_user,
            followed=user
        ).exists()
    except:
        return False


@register.filter
def is_liked_by(post, user):
    """Check if post is liked by user - THIS IS THE NEW MISSING FILTER!"""
    if not user or not user.is_authenticated or not post:
        return False

    try:
        from ..models import SocialPostLike
        return SocialPostLike.objects.filter(
            post=post,
            user=user,
            is_active=True
        ).exists()
    except:
        return False


@register.filter
def is_saved_by(post, user):
    """Check if post is saved by user"""
    if not user or not user.is_authenticated or not post:
        return False

    try:
        from ..models import Save  # Make sure Save model exists
        return Save.objects.filter(
            post=post,
            user=user
        ).exists()
    except:
        return False


# User profile filters
@register.filter
def get_avatar_url(user):
    """Get user's avatar URL"""
    if hasattr(user, 'profile') and user.profile:
        try:
            return user.profile.get_avatar_url()
        except:
            pass
    return '/static/images/default-avatar.png'


@register.filter
def get_display_name(user):
    """Get user's display name"""
    if hasattr(user, 'profile') and user.profile:
        try:
            return user.profile.get_display_name()
        except:
            pass
    return user.username if hasattr(user, 'username') else str(user)


# Number formatting filters
@register.filter
def format_large_number(value):
    """Format large numbers (1.5K, 2.3M)"""
    try:
        if value is None:
            return "0"
        num = int(value)
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        else:
            return str(num)
    except (ValueError, TypeError):
        return str(value) if value else "0"


# Post content filters
@register.filter
def truncate_chars(value, arg):
    """Truncate text to certain number of characters"""
    try:
        if len(value) > arg:
            return value[:arg] + '...'
        return value
    except (TypeError, AttributeError):
        return value


@register.filter
def get_comments_count(post):
    """Get comment count for post"""
    try:
        return post.comments.count()
    except:
        return 0


@register.filter
def get_likes_count(post):
    """Get like count for post"""
    try:
        return post.likes_count
    except:
        return 0


# Time formatting
@register.filter
def time_since(value):
    """Human-readable time since"""
    from django.utils import timezone
    from django.utils.timesince import timesince

    if not value:
        return ""

    try:
        now = timezone.now()
        difference = now - value

        if difference.days == 0:
            if difference.seconds < 60:
                return "just now"
            elif difference.seconds < 3600:
                minutes = difference.seconds // 60
                return f"{minutes}m ago"
            else:
                hours = difference.seconds // 3600
                return f"{hours}h ago"
        elif difference.days == 1:
            return "yesterday"
        elif difference.days < 7:
            return f"{difference.days}d ago"
        elif difference.days < 30:
            weeks = difference.days // 7
            return f"{weeks}w ago"
        else:
            months = difference.days // 30
            return f"{months}mo ago"
    except:
        return str(value)


# templatetags/my_filters.py
from django import template
from django.utils.safestring import mark_safe
import json
from datetime import datetime, timedelta

register = template.Library()


@register.filter
def get_avatar_url(user):
    """Get user avatar URL"""
    if hasattr(user, 'profile'):
        if user.profile.avatar and user.profile.avatar.url:
            return user.profile.avatar.url
        elif user.profile.profile_picture and user.profile.profile_picture.url:
            return user.profile.profile_picture.url
    return '/static/images/default-avatar.png'


@register.filter
def get_display_name(user):
    """Get user display name"""
    if hasattr(user, 'profile'):
        return user.profile.get_display_name()
    return user.get_full_name() or user.username


@register.filter
def is_followed_by(user, requester):
    """Check if user is followed by requester"""
    if not requester.is_authenticated:
        return False
    from My_app.models import FollowRelationship
    return FollowRelationship.objects.filter(
        follower=requester,
        followed=user
    ).exists()


@register.filter
def format_large_number(num):
    """Format large numbers with K/M suffix"""
    if num is None:
        return "0"

    try:
        num = int(num)
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return str(num)
    except:
        return str(num)


@register.filter
def get_user_tags(user):
    """Get user's expertise tags"""
    if hasattr(user, 'profile') and user.profile.trading_style:
        return [user.profile.trading_style]
    return []


@register.filter
def is_online(user):
    """Check if user is online"""
    try:
        return user.user_status.is_online
    except:
        return False


@register.filter
def get_last_activity(user):
    """Get user's last activity time"""
    try:
        return user.user_status.last_seen
    except:
        return user.last_login


@register.filter
def get_trading_days(user):
    """Get user's trading experience in days"""
    if hasattr(user, 'profile'):
        # Calculate days since user joined
        from django.utils import timezone
        days_since_joined = (timezone.now() - user.date_joined).days
        return max(1, days_since_joined)
    return 1