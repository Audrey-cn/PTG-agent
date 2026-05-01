import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import discord
    from discord.ext import commands

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False


class DiscordAdapter(PlatformAdapter):
    platform_type = "discord"
    platform_name = "Discord"
    required_dependencies = ["discord"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.token = self.config.settings.get("token", "")
        self.allowed_channels = self.config.settings.get("allowed_channels", [])
        self._bot = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, channel_id: int | None = None, **kwargs) -> bool:
        if not DISCORD_AVAILABLE or not self._bot:
            logger.warning("Discord: 未连接，无法发送")
            return False
        try:
            target_id = channel_id or (self.allowed_channels[0] if self.allowed_channels else None)
            if target_id:
                channel = self._bot.get_channel(int(target_id))
                if channel:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(channel.send(message[:2000]))
                    else:
                        loop.run_until_complete(channel.send(message[:2000]))
                    return True
            return False
        except Exception as e:
            logger.error("Discord send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not DISCORD_AVAILABLE:
            logger.error("discord.py 未安装: pip install discord.py")
            return False
        if not self.token:
            logger.error("Discord 需要配置 token")
            return False
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            self._bot = commands.Bot(command_prefix="/", intents=intents)

            @self._bot.event
            async def on_ready():
                logger.info("Discord 适配器已启动: %s", self._bot.user)

            @self._bot.event
            async def on_message(message):
                if message.author == self._bot.user:
                    return
                if self.allowed_channels and message.channel.id not in [
                    int(c) for c in self.allowed_channels
                ]:
                    return

                self._pending_messages.append(
                    {
                        "text": message.content,
                        "channel_id": message.channel.id,
                        "user": str(message.author),
                        "platform": "discord",
                    }
                )

                if self._message_handler:
                    try:
                        response = self._message_handler(
                            message.content, channel_id=message.channel.id
                        )
                        if response:
                            await message.channel.send(str(response)[:2000])
                    except Exception as e:
                        logger.error("Message handler error: %s", e)

            import threading

            def _run():
                self._bot.run(self.token)

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
            self._is_running = True
            logger.info("Discord 适配器启动中...")
            return True
        except Exception as e:
            logger.error("Discord 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        if self._bot:
            try:
                import asyncio

                asyncio.run(self._bot.close())
            except Exception:
                pass
        self._is_running = False
        logger.info("Discord 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
