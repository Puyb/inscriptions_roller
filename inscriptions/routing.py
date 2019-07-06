from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from .consumers import MailConsumer

application = ProtocolTypeRouter({
    'channel': ChannelNameRouter({
        'mail': MailConsumer,
    }),
})
