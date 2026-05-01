"""WeCom (企业微信) gateway adapter."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from prometheus.gateway.config import Platform, PlatformConfig
from prometheus.gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_audio_from_bytes,
    cache_document_from_bytes,
    cache_image_from_bytes,
)

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 2048
MAX_MARKDOWN_LENGTH = 2048
CHUNK_SIZE = 600

WECOM_API_BASE = "https://qyapi.weixin.qq.com"

_ACCESS_TOKEN_CACHE: dict[str, tuple[str, float]] = {}

# Supported image extensions
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _check_wecom_deps() -> bool:
    """Return True if httpx is available."""
    try:
        import httpx  # noqa: F401

        return True
    except ImportError:
        return False


def check_wecom_requirements() -> bool:
    """Return True if WeCom is configured."""
    corp_id = os.getenv("WECOM_CORP_ID", "")
    corp_secret = os.getenv("WECOM_CORP_SECRET", "")
    agent_id = os.getenv("WECOM_AGENT_ID", "")
    return bool(corp_id and corp_secret and agent_id) and _check_wecom_deps()


def _get_access_token(corp_id: str, corp_secret: str) -> str | None:
    """Get or refresh WeCom access token with caching."""
    cache_key = f"{corp_id}:{corp_secret}"
    if cache_key in _ACCESS_TOKEN_CACHE:
        token, expires_at = _ACCESS_TOKEN_CACHE[cache_key]
        if time.time() < expires_at - 60:
            return token

    url = f"{WECOM_API_BASE}/cgi-bin/gettoken"
    params = {"corpid": corp_id, "corpsecret": corp_secret}
    try:
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) == 0:
            token = data["access_token"]
            expires_in = int(data.get("expires_in", 7200))
            _ACCESS_TOKEN_CACHE[cache_key] = (token, time.time() + expires_in)
            return token
        logger.warning("WeCom: gettoken failed: %s", data)
        return None
    except Exception as e:
        logger.error("WeCom: gettoken error: %s", e)
        return None


class WeComAdapter(BasePlatformAdapter):
    """WeCom gateway adapter for receiving and sending messages."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.WECOM)

        extra = config.extra or {}
        self._corp_id = extra.get("corp_id") or os.getenv("WECOM_CORP_ID", "")
        self._corp_secret = extra.get("corp_secret") or os.getenv("WECOM_CORP_SECRET", "")
        self._agent_id = extra.get("agent_id") or os.getenv("WECOM_AGENT_ID", "")
        self._webhook_secret = extra.get("webhook_secret") or os.getenv("WECOM_WEBHOOK_SECRET", "")
        self._webhook_key = extra.get("webhook_key") or os.getenv("WECOM_WEBHOOK_KEY", "")
        self._encrypt_mode = extra.get("encrypt_mode", "safe")
        self._encoding_aes_key = extra.get("encoding_aes_key") or os.getenv(
            "WECOM_ENCODING_AES_KEY", ""
        )
        self._token = extra.get("token") or os.getenv("WECOM_TOKEN", "")

        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._poll_task: asyncio.Task | None = None

        # Track processed message IDs to avoid duplicates
        self._processed_msg_ids: set = set()
        self._processed_msg_ids_max: int = 1000

        logger.info(
            "WeCom adapter initialized: corp_id=%s agent_id=%s encrypt_mode=%s",
            self._corp_id,
            self._agent_id,
            self._encrypt_mode,
        )

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Initialize WeCom API client."""
        if not self._corp_id or not self._corp_secret or not self._agent_id:
            logger.error("WeCom: corp_id, corp_secret, and agent_id are required")
            return False

        self._client = httpx.AsyncClient(timeout=30)
        self._access_token = _get_access_token(self._corp_id, self._corp_secret)
        if not self._access_token:
            logger.error("WeCom: failed to get access token")
            return False

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._mark_connected()
        logger.info("WeCom: connected")
        return True

    async def disconnect(self) -> None:
        """Disconnect from WeCom."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("WeCom: disconnected")

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send a text or markdown message via WeCom API."""
        if not content:
            return SendResult(success=True)

        formatted = self.format_message(content)
        chunks = self.truncate_message(formatted, CHUNK_SIZE)

        last_msg_id = None
        for chunk in chunks:
            msg_id = await self._send_message(chat_id, chunk)
            if msg_id:
                last_msg_id = msg_id
            else:
                return SendResult(success=False, error="Failed to send message")

        return SendResult(success=True, message_id=last_msg_id)

    async def _send_message(self, to_user: str, content: str) -> str | None:
        """Send a single message via WeCom message API."""
        if not self._access_token:
            self._access_token = _get_access_token(self._corp_id, self._corp_secret)
            if not self._access_token:
                return None

        url = f"{WECOM_API_BASE}/cgi-bin/message/send"
        params = {"access_token": self._access_token}

        # Detect markdown content
        is_markdown = bool(re.search(r"^#{1,6}\s|```|\*\*|\*|>-", content, re.MULTILINE))

        msgtype = "markdown" if is_markdown else "text"
        payload: dict[str, Any] = {
            "touser": to_user,
            "msgtype": msgtype,
            "agentid": self._agent_id,
            msgtype: {"content": content},
        }

        try:
            resp = await self._client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("errcode", 0) == 0:
                return data.get("msgid")
            elif data.get("errcode") in (40014, 40001, 42001):
                # Invalid token — refresh and retry once
                self._access_token = _get_access_token(self._corp_id, self._corp_secret)
                if self._access_token:
                    params["access_token"] = self._access_token
                    resp = await self._client.post(url, params=params, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    if data.get("errcode", 0) == 0:
                        return data.get("msgid")
            logger.warning("WeCom: send failed: %s", data)
            return None
        except Exception as e:
            logger.error("WeCom: send error: %s", e)
            return None

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """Return basic chat info."""
        return {
            "name": chat_id,
            "type": "dm",
            "chat_id": chat_id,
        }

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    def format_message(self, content: str) -> str:
        """Convert Markdown to WeCom markdown format."""
        # WeCom markdown supports limited subset:
        # # Heading, **bold**, *italic*, `code`, ```code block```,
        # - list, > quote, [text](url)
        result = content

        # Strip image markdown: ![alt](url) → url
        result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", result)

        # Convert ```lang\n...\n``` → ```\n...\n```
        result = re.sub(r"```\w*\n?", "```", result)

        # Convert ***bold+italic*** → **bold** (WeCom doesn't support triple asterisk)
        result = re.sub(r"\*{3}(.+?)\*{3}", r"**\1**", result)

        # Convert __underline__ → ** (no underline in WeCom)
        result = re.sub(r"_{2}(.+?)_{2}", r"**\1**", result)

        # Convert ~~strikethrough~~ → ~~ (WeCom doesn't support)
        result = re.sub(r"~~(.+?)~~", r"\1", result)

        # Convert - [ ] task → - □ task (WeCom doesn't support checkbox)
        result = re.sub(r"-\s*\[\s*\]", "- □", result)
        result = re.sub(r"-\s*\[x\]", "- ■", result)

        # Strip unsupported HTML tags
        result = re.sub(r"</?div[^>]*>", "", result)
        result = re.sub(r"</?span[^>]*>", "", result)

        return result

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Download image and send via WeCom image API."""
        if image_url.startswith("http"):
            try:
                from prometheus.tools.url_safety import is_safe_url

                if not is_safe_url(image_url):
                    return SendResult(success=False, error="URL not allowed")
                resp = await self._client.get(image_url, timeout=30)
                resp.raise_for_status()
                image_data = resp.content
                media_id = await self._upload_media(image_data, "image")
            except Exception as e:
                logger.warning("WeCom: failed to download image: %s", e)
                text = caption or ""
                if image_url:
                    text += f"\n{image_url}"
                return await self.send(chat_id, text.strip())
        elif image_url.startswith("file://"):
            path = unquote(image_url[7:])
            try:
                image_data = Path(path).read_bytes()
                media_id = await self._upload_media(image_data, "image")
            except Exception as e:
                return SendResult(success=False, error=str(e))
        else:
            return SendResult(success=False, error="Unsupported image URL scheme")

        if not media_id:
            return SendResult(success=False, error="Failed to upload image")

        msg_id = await self._send_media_message(chat_id, "image", media_id, caption)
        if msg_id:
            return SendResult(success=True, message_id=msg_id)
        return SendResult(success=False, error="Failed to send image")

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send a local image file via WeCom."""
        p = Path(image_path)
        if not p.exists():
            return SendResult(success=False, error="File not found")
        try:
            image_data = p.read_bytes()
            media_id = await self._upload_media(image_data, "image")
        except Exception as e:
            return SendResult(success=False, error=str(e))

        if not media_id:
            return SendResult(success=False, error="Failed to upload image")
        msg_id = await self._send_media_message(chat_id, "image", media_id, caption)
        if msg_id:
            return SendResult(success=True, message_id=msg_id)
        return SendResult(success=False, error="Failed to send image")

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: str | None = None,
        file_name: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Upload and send a file via WeCom file API."""
        p = Path(file_path)
        if not p.exists():
            return SendResult(success=False, error="File not found")

        try:
            file_data = p.read_bytes()
            ext = p.suffix.lower()
            if ext in _IMAGE_EXTS:
                media_id = await self._upload_media(file_data, "image")
                msgtype = "image"
            else:
                media_id = await self._upload_media(file_data, "file")
                msgtype = "file"
        except Exception as e:
            return SendResult(success=False, error=str(e))

        if not media_id:
            return SendResult(success=False, error="Failed to upload file")

        msg_id = await self._send_media_message(chat_id, msgtype, media_id, caption)
        if msg_id:
            return SendResult(success=True, message_id=msg_id)
        return SendResult(success=False, error="Failed to send file")

    async def send_audio(
        self,
        chat_id: str,
        audio_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Upload and send a voice file via WeCom voice API."""
        p = Path(audio_path)
        if not p.exists():
            return SendResult(success=False, error="File not found")
        try:
            audio_data = p.read_bytes()
            media_id = await self._upload_media(audio_data, "voice")
        except Exception as e:
            return SendResult(success=False, error=str(e))

        if not media_id:
            return SendResult(success=False, error="Failed to upload voice")

        msg_id = await self._send_media_message(chat_id, "voice", media_id, caption)
        if msg_id:
            return SendResult(success=True, message_id=msg_id)
        return SendResult(success=False, error="Failed to send voice")

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Upload and send a video via WeCom video API."""
        p = Path(video_path)
        if not p.exists():
            return SendResult(success=False, error="File not found")
        try:
            video_data = p.read_bytes()
            media_id = await self._upload_media(video_data, "video")
        except Exception as e:
            return SendResult(success=False, error=str(e))

        if not media_id:
            return SendResult(success=False, error="Failed to upload video")

        msg_id = await self._send_media_message(chat_id, "video", media_id, caption)
        if msg_id:
            return SendResult(success=True, message_id=msg_id)
        return SendResult(success=False, error="Failed to send video")

    # ------------------------------------------------------------------
    # Media upload and send helpers
    # ------------------------------------------------------------------

    async def _upload_media(self, data: bytes, media_type: str) -> str | None:
        """Upload media to WeCom and return media_id."""
        if not self._access_token:
            self._access_token = _get_access_token(self._corp_id, self._corp_secret)
            if not self._access_token:
                return None

        url = f"{WECOM_API_BASE}/cgi-bin/media/upload"
        params = {"access_token": self._access_token, "type": media_type}

        try:
            import io

            files = {"file": ("media", io.BytesIO(data), "application/octet-stream")}
            resp = await self._client.post(url, params=params, files=files)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode", 0) == 0:
                return result.get("media_id")
            logger.warning("WeCom: upload failed: %s", result)
            return None
        except Exception as e:
            logger.error("WeCom: upload error: %s", e)
            return None

    async def _send_media_message(
        self,
        to_user: str,
        msgtype: str,
        media_id: str,
        caption: str | None = None,
    ) -> str | None:
        """Send a media message via WeCom API."""
        if not self._access_token:
            self._access_token = _get_access_token(self._corp_id, self._corp_secret)
            if not self._access_token:
                return None

        url = f"{WECOM_API_BASE}/cgi-bin/message/send"
        params = {"access_token": self._access_token}

        content_key = msgtype
        content_value = {"media_id": media_id}
        if caption and msgtype == "text":
            content_value = {"content": caption}

        payload: dict[str, Any] = {
            "touser": to_user,
            "msgtype": msgtype,
            "agentid": self._agent_id,
            content_key: content_value,
        }

        try:
            resp = await self._client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode", 0) == 0:
                return data.get("msgid")
            logger.warning("WeCom: send media failed: %s", data)
            return None
        except Exception as e:
            logger.error("WeCom: send media error: %s", e)
            return None

    # ------------------------------------------------------------------
    # Webhook / polling for inbound messages
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Poll for incoming messages via webhook or long polling."""
        while self._running:
            try:
                await self._poll_webhook()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("WeCom: poll error: %s", e)
            await asyncio.sleep(5)

    async def _poll_webhook(self) -> None:
        """Poll WeCom for incoming webhook events."""
        if not self._webhook_key:
            return

        url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/sync_messages"
        params = {
            "access_token": self._access_token,
            "agentid": self._agent_id,
        }

        try:
            resp = await self._client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.warning("WeCom: sync_messages failed: %s", data)
                return

            msg_list = data.get("msg_list", [])
            for msg_data in msg_list:
                await self._handle_webhook_message(msg_data)
        except Exception as e:
            logger.warning("WeCom: webhook poll error: %s", e)

    async def _handle_webhook_message(self, msg_data: dict[str, Any]) -> None:
        """Process an incoming WeCom webhook message."""
        msg_id = msg_data.get("msgid") or msg_data.get("MsgId", "")
        if msg_id in self._processed_msg_ids:
            return
        self._processed_msg_ids.add(msg_id)
        if len(self._processed_msg_ids) > self._processed_msg_ids_max:
            self._processed_msg_ids = set(
                list(self._processed_msg_ids)[-self._processed_msg_ids_max // 2 :]
            )

        msg_type = msg_data.get("msg_type") or msg_data.get("MsgType", "")
        from_user = msg_data.get("from_user") or msg_data.get("FromUserName", "")
        msg_data.get("to_user") or msg_data.get("ToUserName", "")
        content = msg_data.get("content") or msg_data.get("Content", "")

        if not content and msg_type == "text":
            return

        chat_id = from_user
        text = content.strip()
        msg_type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.PHOTO,
            "voice": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "file": MessageType.DOCUMENT,
        }
        msg_type_enum = msg_type_map.get(msg_type, MessageType.TEXT)

        media_urls = None
        media_types = None
        if msg_type in ("image", "voice", "video", "file"):
            media_id = msg_data.get("media_id") or msg_data.get("MediaId", "")
            if media_id:
                media_path = await self._download_media(media_id, msg_type)
                if media_path:
                    media_urls = [media_path]
                    media_type_map = {
                        "image": "image/png",
                        "voice": "audio/ogg",
                        "video": "video/mp4",
                        "file": "application/octet-stream",
                    }
                    media_types = [media_type_map.get(msg_type, "application/octet-stream")]

        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_id,
            chat_type="dm",
            user_id=chat_id,
            user_name=chat_id,
        )

        event = MessageEvent(
            text=text,
            message_type=msg_type_enum,
            source=source,
            message_id=msg_id,
            media_urls=media_urls,
            media_types=media_types,
            raw_message=msg_data,
        )

        await self.handle_message(event)

    async def _download_media(self, media_id: str, media_type: str) -> str | None:
        """Download media from WeCom and cache it locally."""
        if not self._access_token:
            return None

        url = f"{WECOM_API_BASE}/cgi-bin/media/get"
        params = {"access_token": self._access_token, "media_id": media_id}

        try:
            resp = await self._client.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.content

            # Check if response is JSON (error) or binary
            try:
                json_data = json.loads(data)
                if json_data.get("errcode"):
                    logger.warning("WeCom: download media failed: %s", json_data)
                    return None
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

            if media_type == "image":
                return cache_image_from_bytes(data, ".jpg")
            elif media_type == "voice":
                return cache_audio_from_bytes(data, ".ogg")
            elif media_type == "video":
                return cache_document_from_bytes(data, "video.mp4")
            else:
                return cache_document_from_bytes(data, "file")
        except Exception as e:
            logger.error("WeCom: download media error: %s", e)
            return None
