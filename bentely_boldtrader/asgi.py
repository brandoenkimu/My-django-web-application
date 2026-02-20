import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
import My_app.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bentely_boldtrader.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            My_app.routing.websocket_urlpatterns
        )
    ),
})