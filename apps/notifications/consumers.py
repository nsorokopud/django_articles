import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            self.group = self.user.username
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, code) -> None:
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def send_notification(self, event) -> None:
        await self.send(
            text_data=json.dumps(
                {
                    "id": event["id"],
                    "title": event["title"],
                    "text": event["message"],
                    "link": event["link"],
                    "timestamp": event["timestamp"],
                }
            )
        )
