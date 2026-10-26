from django.urls import path

from .views import ChatPanelView, ChatView, chat_api, limpiar_chat

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("chat/panel/", ChatPanelView.as_view(), name="chat_panel"),
    path("api/chat/", chat_api, name="chat_api"),
    path("api/chat/limpiar/", limpiar_chat, name="chat_limpiar"),
]
