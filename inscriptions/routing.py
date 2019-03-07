from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from .consumers import send_mail

application = ProtocolTypeRouter({
    'channels': ChannelNameRouter({
        'send-mail': send_mail,
    }),
})
