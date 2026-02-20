from rest_framework import serializers
from .models import KYCApplication, Transaction, Profile, Wallet


class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCApplication
        fields = '__all__'
        read_only_fields = ['user', 'submitted_at', 'status']


class TransactionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['reference', 'created_at', 'updated_at', 'transaction_id']


class ProfileSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']


class WalletSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Wallet
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']