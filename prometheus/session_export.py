"""Session export functionality for Prometheus."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.session_export")


class SessionExporter:
    """Export sessions in various formats."""

    def export_json(
        self,
        session_data: dict[str, Any],
        output_path: Path,
        pretty: bool = True,
    ) -> None:
        """Export session to JSON format.

        Args:
            session_data: Session data dictionary
            output_path: Path to export to
            pretty: Whether to pretty-print
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(session_data, f, ensure_ascii=False)

        logger.info(f"Exported session to JSON: {output_path}")

    def export_markdown(
        self,
        session_data: dict[str, Any],
        output_path: Path,
        include_metadata: bool = True,
    ) -> None:
        """Export session to Markdown format.

        Args:
            session_data: Session data dictionary
            output_path: Path to export to
            include_metadata: Whether to include metadata
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []

        if include_metadata:
            lines.append("# Session Export")
            lines.append("")
            lines.append(f"**Session ID:** {session_data.get('session_id', 'N/A')}")
            lines.append(f"**Created:** {session_data.get('created_at', 'N/A')}")
            lines.append(f"**Last Accessed:** {session_data.get('last_accessed', 'N/A')}")
            lines.append(f"**Title:** {session_data.get('title', 'Untitled')}")
            lines.append("")
            lines.append("---")
            lines.append("")

        messages = session_data.get("messages", [])

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = "\n".join(text_parts)

            lines.append(f"## {role.upper()}")
            lines.append("")
            lines.append(content)
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Exported session to Markdown: {output_path}")

    def export_text(
        self,
        session_data: dict[str, Any],
        output_path: Path,
    ) -> None:
        """Export session to plain text format.

        Args:
            session_data: Session data dictionary
            output_path: Path to export to
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("=" * 80)
        lines.append(f"SESSION: {session_data.get('session_id', 'N/A')}")
        lines.append(f"DATE: {session_data.get('created_at', 'N/A')}")
        lines.append("=" * 80)
        lines.append("")

        messages = session_data.get("messages", [])

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = "\n".join(text_parts)

            lines.append(f"[{role.upper()}]")
            lines.append("-" * 40)
            lines.append(content)
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Exported session to text: {output_path}")

    def export_html(
        self,
        session_data: dict[str, Any],
        output_path: Path,
        theme: str = "light",
    ) -> None:
        """Export session to HTML format.

        Args:
            session_data: Session data dictionary
            output_path: Path to export to
            theme: Color theme (light/dark)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        messages = session_data.get("messages", [])

        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>Session: {session_data.get('title', 'Untitled')}</title>",
            "<meta charset='UTF-8'>",
            "<style>",
            f"body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: {'#1a1a2e' if theme == 'dark' else '#f5f5f5'}; color: {'#e0e0e0' if theme == 'dark' else '#333'}; }}",
            ".message {{ background: {'#2a2a3e' if theme == 'dark' else '#fff'}; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}",
            ".role {{ font-weight: bold; font-size: 14px; margin-bottom: 8px; text-transform: uppercase; }}",
            ".user .role {{ color: #667eea; }}",
            ".assistant .role {{ color: #f5576c; }}",
            ".content {{ font-size: 16px; line-height: 1.6; white-space: pre-wrap; }}",
            ".metadata {{ font-size: 12px; color: #888; margin-top: 12px; }}",
            ".header {{ text-align: center; margin-bottom: 40px; }}",
            ".header h1 {{ color: #e94560; }}",
            "</style>",
            "</head>",
            "<body>",
            "<div class='header'>",
            f"<h1>🔮 {session_data.get('title', 'Untitled Session')}</h1>",
            f"<p class='metadata'>Session ID: {session_data.get('session_id', 'N/A')}</p>",
            f"<p class='metadata'>Created: {session_data.get('created_at', 'N/A')}</p>",
            "</div>",
        ]

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = "\n".join(text_parts)

            html_lines.append(f"<div class='message {role}'>")
            html_lines.append(f"<div class='role'>{role}</div>")
            html_lines.append(f"<div class='content'>{self._escape_html(content)}</div>")
            html_lines.append("</div>")

        html_lines.extend(
            [
                "</body>",
                "</html>",
            ]
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))

        logger.info(f"Exported session to HTML: {output_path}")

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


class BatchSessionExporter:
    """Export multiple sessions in batch."""

    def __init__(self, exporter: SessionExporter | None = None):
        self._exporter = exporter or SessionExporter()

    def export_all(
        self,
        sessions: list[dict[str, Any]],
        output_dir: Path,
        format: str = "json",
        include_metadata: bool = True,
    ) -> list[Path]:
        """Export multiple sessions.

        Args:
            sessions: List of session data dictionaries
            output_dir: Directory to export to
            format: Export format (json/markdown/text/html)
            include_metadata: Whether to include metadata

        Returns:
            List of exported file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_paths = []

        for session in sessions:
            session_id = session.get("session_id", "unknown")
            output_path = output_dir / f"{session_id}.{format}"

            if format == "json":
                self._exporter.export_json(session, output_path)
            elif format == "markdown":
                self._exporter.export_markdown(session, output_path, include_metadata)
            elif format == "text":
                self._exporter.export_text(session, output_path)
            elif format == "html":
                self._exporter.export_html(session, output_path)

            exported_paths.append(output_path)

        logger.info(f"Exported {len(exported_paths)} sessions to {output_dir}")
        return exported_paths


def export_session(
    session_data: dict[str, Any],
    output_path: Path,
    format: str = "json",
    **kwargs,
) -> None:
    """Export a single session.

    Args:
        session_data: Session data dictionary
        output_path: Path to export to
        format: Export format (json/markdown/text/html)
        **kwargs: Additional format-specific arguments
    """
    exporter = SessionExporter()

    if format == "json":
        exporter.export_json(session_data, output_path, **kwargs)
    elif format == "markdown":
        exporter.export_markdown(session_data, output_path, **kwargs)
    elif format == "text":
        exporter.export_text(session_data, output_path)
    elif format == "html":
        exporter.export_html(session_data, output_path, **kwargs)
    else:
        raise ValueError(f"Unknown format: {format}")


def export_all_sessions(
    output_dir: Path,
    format: str = "json",
) -> list[Path]:
    """Export all sessions.

    Args:
        output_dir: Directory to export to
        format: Export format (json/markdown/text/html)

    Returns:
        List of exported file paths
    """
    from .session_manager import get_session_browser

    browser = get_session_browser()
    sessions = browser.browse(limit=1000)

    exported_paths = []
    exporter = BatchSessionExporter()

    for session_summary in sessions:
        session_id = session_summary.get("session_id")
        session_detail = browser.get_session_detail(session_id)

        if session_detail:
            session_path = output_dir / f"{session_id}.{format}"

            if format == "json":
                exporter.export_json(session_detail, session_path)
            elif format == "markdown":
                exporter.export_markdown(session_detail, session_path)
            elif format == "text":
                exporter.export_text(session_detail, session_path)
            elif format == "html":
                exporter.export_html(session_detail, session_path)

            exported_paths.append(session_path)

    return exported_paths
