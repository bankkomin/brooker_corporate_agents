"""Unit tests for services/shared/mermaid_render.py.

All external calls (httpx, subprocess) are mocked — no real network or
mmdc binary required.
"""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.shared.mermaid_render import (
    render_mermaid_png,
    render_mermaid_via_ink,
    render_mermaid_via_mmdc,
    save_mermaid,
    validate_mermaid_syntax,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid PNG: 8-byte magic + empty IHDR (content doesn't need to be
# valid PNG structure — we only test the magic-byte check).
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _b64_of(text: str) -> str:
    """Return the URL-safe base64 encoding of ``text``."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# validate_mermaid_syntax
# ---------------------------------------------------------------------------


class TestValidateMermaidSyntax:
    def test_recognises_graph(self) -> None:
        assert validate_mermaid_syntax("graph LR\nA-->B") is True

    def test_recognises_flowchart(self) -> None:
        assert validate_mermaid_syntax("flowchart TD\nA-->B") is True

    def test_recognises_sequence_diagram(self) -> None:
        assert validate_mermaid_syntax("sequenceDiagram\nA->>B: hi") is True

    def test_recognises_class_diagram(self) -> None:
        assert validate_mermaid_syntax("classDiagram\nAnimal <|-- Duck") is True

    def test_recognises_state_diagram(self) -> None:
        assert validate_mermaid_syntax("stateDiagram\n[*] --> Still") is True

    def test_recognises_gantt(self) -> None:
        assert validate_mermaid_syntax("gantt\ntitle Project") is True

    def test_recognises_pie(self) -> None:
        assert validate_mermaid_syntax("pie\ntitle Langs") is True

    def test_recognises_journey(self) -> None:
        assert validate_mermaid_syntax("journey\ntitle My day") is True

    def test_recognises_mindmap(self) -> None:
        assert validate_mermaid_syntax("mindmap\nroot") is True

    def test_recognises_git_graph(self) -> None:
        assert validate_mermaid_syntax("gitGraph\ncommit") is True

    def test_recognises_er_diagram(self) -> None:
        assert validate_mermaid_syntax("erDiagram\nCUSTOMER ||--o{ ORDER : places") is True

    def test_rejects_unknown_keyword(self) -> None:
        assert validate_mermaid_syntax("noSuchDiagram\nfoo") is False

    def test_rejects_empty_string(self) -> None:
        assert validate_mermaid_syntax("") is False

    def test_rejects_whitespace_only(self) -> None:
        assert validate_mermaid_syntax("   \n\n\t  ") is False

    def test_skips_leading_comment_lines(self) -> None:
        """Lines starting with %% are Mermaid comments and should be skipped."""
        text = "%% This is a comment\ngraph LR\nA-->B"
        assert validate_mermaid_syntax(text) is True

    def test_rejects_html_fragment(self) -> None:
        assert validate_mermaid_syntax("<html><body>Error</body></html>") is False


# ---------------------------------------------------------------------------
# render_mermaid_via_ink
# ---------------------------------------------------------------------------


class TestRenderViaMermaidInk:
    def test_makes_correct_url(self) -> None:
        """URL must contain the URL-safe base64 of the input and the theme param."""
        diagram = "graph LR\nA-->B"
        expected_b64 = _b64_of(diagram)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = _FAKE_PNG

        with patch("httpx.get", return_value=mock_response) as mock_get:
            result = render_mermaid_via_ink(diagram, theme="neutral", background="white")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url: str = call_args.args[0]
        params: dict[str, str] = call_args.kwargs["params"]

        assert expected_b64 in url, f"Expected base64 {expected_b64!r} in URL {url!r}"
        assert params.get("theme") == "neutral"
        assert result == _FAKE_PNG

    def test_raises_on_non_png_response(self) -> None:
        """An HTML error page must raise RuntimeError, not be returned."""
        html_body = b"<html><body>Rate limit exceeded</body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = html_body

        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="not a PNG"):
                render_mermaid_via_ink("graph LR\nA-->B")

    def test_raises_on_non_200_status(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"

        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="429"):
                render_mermaid_via_ink("graph LR\nA-->B")

    def test_raises_on_timeout(self) -> None:
        """A timeout from httpx must surface as RuntimeError mentioning 'timed out'."""
        import httpx as _httpx

        with patch("httpx.get", side_effect=_httpx.TimeoutException("timed out")):
            with pytest.raises(RuntimeError, match="timed out"):
                render_mermaid_via_ink("graph LR\nA-->B")

    def test_raises_on_request_error(self) -> None:
        import httpx as _httpx

        with patch("httpx.get", side_effect=_httpx.RequestError("connection refused")):
            with pytest.raises(RuntimeError, match="request failed"):
                render_mermaid_via_ink("graph LR\nA-->B")

    def test_respects_mermaid_ink_url_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MERMAID_INK_URL env var overrides the default endpoint."""
        monkeypatch.setenv("MERMAID_INK_URL", "http://ink.internal")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = _FAKE_PNG

        with patch("httpx.get", return_value=mock_response) as mock_get:
            render_mermaid_via_ink("graph LR\nA-->B")

        url: str = mock_get.call_args.args[0]
        assert url.startswith("http://ink.internal"), url

    def test_raises_when_output_exceeds_cap(self) -> None:
        """A response larger than 25 MB must be rejected."""
        oversized = _FAKE_PNG + b"\x00" * (25 * 1024 * 1024 + 1)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = oversized

        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="25 MB"):
                render_mermaid_via_ink("graph LR\nA-->B")


# ---------------------------------------------------------------------------
# render_mermaid_via_mmdc
# ---------------------------------------------------------------------------


class TestRenderViaMmdc:
    def _make_subprocess_mock(self, returncode: int = 0, stderr: str = "") -> MagicMock:
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stderr = stderr
        return mock_result

    def test_subprocess_call_args(self, tmp_path: Path) -> None:
        """mmdc must be called with the right flags."""
        with patch("subprocess.run", return_value=self._make_subprocess_mock()) as mock_run, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=_FAKE_PNG):

            render_mermaid_via_mmdc(
                "graph LR\nA-->B",
                "/usr/local/bin/mmdc",
                theme="dark",
                background="#000000",
                width=800,
            )

        mock_run.assert_called_once()
        cmd: list[str] = mock_run.call_args.args[0]

        assert cmd[0] == "/usr/local/bin/mmdc"
        assert "-i" in cmd
        assert "-o" in cmd
        assert "--theme" in cmd
        assert "dark" in cmd
        assert "--backgroundColor" in cmd
        assert "#000000" in cmd
        assert "--width" in cmd
        assert "800" in cmd

    def test_raises_on_nonzero_exit(self) -> None:
        """A non-zero mmdc exit must raise RuntimeError with the stderr included."""
        with patch("subprocess.run", return_value=self._make_subprocess_mock(
            returncode=1, stderr="Syntax error in diagram"
        )):
            with pytest.raises(RuntimeError, match="Syntax error in diagram"):
                render_mermaid_via_mmdc(
                    "badDiagram\n???",
                    "/usr/local/bin/mmdc",
                )

    def test_raises_when_output_file_missing(self) -> None:
        """If mmdc exits 0 but writes no file, raise RuntimeError."""
        with patch("subprocess.run", return_value=self._make_subprocess_mock(returncode=0)), \
             patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="output file not found"):
                render_mermaid_via_mmdc("graph LR\nA-->B", "/usr/local/bin/mmdc")

    def test_raises_on_non_png_output(self) -> None:
        """Even if mmdc exits 0, a non-PNG output file must raise RuntimeError."""
        with patch("subprocess.run", return_value=self._make_subprocess_mock(returncode=0)), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"JFIF garbage"):
            with pytest.raises(RuntimeError, match="not a PNG"):
                render_mermaid_via_mmdc("graph LR\nA-->B", "/usr/local/bin/mmdc")


# ---------------------------------------------------------------------------
# render_mermaid_png — backend selection
# ---------------------------------------------------------------------------


class TestRenderMermaidPng:
    def test_prefers_mmdc_when_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MERMAID_CLI_PATH is set, mmdc must be used and ink must NOT be called."""
        monkeypatch.setenv("MERMAID_CLI_PATH", "/usr/local/bin/mmdc")

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_mmdc",
            return_value=_FAKE_PNG,
        ) as mock_mmdc, patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
        ) as mock_ink:
            result = render_mermaid_png("graph LR\nA-->B")

        mock_mmdc.assert_called_once()
        mock_ink.assert_not_called()
        assert result == _FAKE_PNG

    def test_falls_back_to_ink_when_mmdc_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MERMAID_CLI_PATH is absent, the ink HTTP path must be used."""
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ) as mock_ink, patch(
            "services.shared.mermaid_render.render_mermaid_via_mmdc",
        ) as mock_mmdc:
            result = render_mermaid_png("graph LR\nA-->B")

        mock_ink.assert_called_once()
        mock_mmdc.assert_not_called()
        assert result == _FAKE_PNG

    def test_falls_back_to_ink_when_mmdc_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty MERMAID_CLI_PATH must be treated the same as unset."""
        monkeypatch.setenv("MERMAID_CLI_PATH", "   ")

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ) as mock_ink:
            render_mermaid_png("graph LR\nA-->B")

        mock_ink.assert_called_once()

    def test_passes_theme_and_background_to_mmdc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MERMAID_CLI_PATH", "/usr/local/bin/mmdc")

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_mmdc",
            return_value=_FAKE_PNG,
        ) as mock_mmdc:
            render_mermaid_png(
                "graph LR\nA-->B", theme="dark", background="#111111", width=640
            )

        call_kwargs = mock_mmdc.call_args.kwargs
        assert call_kwargs["theme"] == "dark"
        assert call_kwargs["background"] == "#111111"
        assert call_kwargs["width"] == 640

    def test_passes_theme_and_background_to_ink(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ) as mock_ink:
            render_mermaid_png("graph LR\nA-->B", theme="neutral", background="grey")

        call_kwargs = mock_ink.call_args.kwargs
        assert call_kwargs["theme"] == "neutral"
        assert call_kwargs["background"] == "grey"


# ---------------------------------------------------------------------------
# save_mermaid
# ---------------------------------------------------------------------------


class TestSaveMermaid:
    def test_writes_file_with_png_magic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save_mermaid must write the rendered bytes to disk."""
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)
        out_file = tmp_path / "out.png"

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ):
            result = save_mermaid("graph LR\nA-->B", out_file)

        assert result == out_file
        assert out_file.exists()
        assert out_file.read_bytes() == _FAKE_PNG
        assert out_file.read_bytes()[:4] == b"\x89PNG"

    def test_creates_parent_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)
        nested_path = tmp_path / "a" / "b" / "c" / "diagram.png"

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ):
            result = save_mermaid("graph LR\nA-->B", nested_path)

        assert result.exists()

    def test_accepts_str_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)
        out_file = str(tmp_path / "str_path.png")

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ):
            result = save_mermaid("graph LR\nA-->B", out_file)

        assert isinstance(result, Path)
        assert result.exists()

    def test_forwards_kwargs_to_render(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MERMAID_CLI_PATH", raising=False)
        out_file = tmp_path / "kwargs.png"

        with patch(
            "services.shared.mermaid_render.render_mermaid_via_ink",
            return_value=_FAKE_PNG,
        ) as mock_ink:
            save_mermaid(
                "graph LR\nA-->B", out_file, theme="dark", background="black"
            )

        call_kwargs = mock_ink.call_args.kwargs
        assert call_kwargs["theme"] == "dark"
        assert call_kwargs["background"] == "black"
