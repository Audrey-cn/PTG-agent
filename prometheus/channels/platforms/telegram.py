import asyncio
import logging
import re
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


_MDV2_ESCAPE_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')


def _escape_mdv2(text: str) -> str:
    return _MDV2_ESCAPE_RE.sub(r'\\\1', text)


class TelegramAdapter(PlatformAdapter):
    platform_type = "telegram"
    platform_name = "Telegram"
    required_dependencies = ["telegram"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.token = self.config.settings.get("token", "")
        self.allowed_chat_ids = self.config.settings.get("allowed_chat_ids", [])
        self._application = None
        self._bot = None
        self._message_handler = None
        self._pending_messages: list = []

    def send(self, message: str, chat_id: int | None = None, **kwargs) -> bool:
        if not TELEGRAM_AVAILABLE or not self._bot:
            logger.warning("Telegram: 未连接，无法发送")
            return False
        target = chat_id or (self.allowed_chat_ids[0] if self.allowed_chat_ids else None)
        if not target:
            logger.warning("Telegram: 无目标 chat_id")
            return False
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._bot.send_message(
                    chat_id=target,
                    text=message[:4096],
                    parse_mode=ParseMode.MARKDOWN_V2 if kwargs.get("markdown") else None,
                ))
            else:
                loop.run_until_complete(self._bot.send_message(
                    chat_id=target,
                    text=message[:4096],
                    parse_mode=ParseMode.MARKDOWN_V2 if kwargs.get("markdown") else None,
                ))
            return True
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(
                content=msg.get("text", ""),
                metadata=msg,
            )
        return None

    def start(self) -> bool:
        if not TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot 未安装: pip install python-telegram-bot")
            return False
        if not self.token:
            logger.error("Telegram 需要配置 token")
            return False
        try:
            self._application = (
                Application.builder()
                .token(self.token)
                .build()
            )
            self._bot = self._application.bot

            self._application.add_handler(CommandHandler("start", self._cmd_start))
            self._application.add_handler(CommandHandler("help", self._cmd_help))
            self._application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
            )

            import threading
            def _run():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._application.initialize())
                loop.run_until_complete(self._application.start())
                loop.run_until_complete(self._application.updater.start_polling())
                loop.run_forever()

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
            self._is_running = True
            logger.info("Telegram 适配器已启动")
            return True
        except Exception as e:
            logger.error("Telegram 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        if self._application:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._application.stop())
            except Exception:
                pass
        self._is_running = False
        logger.info("Telegram 适配器已停止")
        return True

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🔥 Prometheus 已就绪！发送消息开始对话。"
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🔥 Prometheus 命令:\n"
            "/start - 开始\n"
            "/help - 帮助\n"
            "直接发送消息与 AI 对话"
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return

        text = update.message.text or ""
        if not text:
            return

        self._pending_messages.append({
            "text": text,
            "chat_id": chat_id,
            "user": update.effective_user.username or str(update.effective_user.id),
            "platform": "telegram",
        })

        if self._message_handler:
            try:
                response = self._message_handler(text, chat_id=chat_id)
                if response:
                    await update.message.reply_text(str(response)[:4096])
            except Exception as e:
                logger.error("Message handler error: %s", e)

    def set_message_handler(self, handler):
        self._message_handler = handler
