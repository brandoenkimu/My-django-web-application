# My_app/apps.py
from django.apps import AppConfig


class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'My_app'  # Make sure this matches your app name exactly

    def ready(self):
        # Import signals inside ready() method
        try:
            import My_app.signals
        except ImportError:
            pass