import base64

import pytest

from skills.qr_generate import QrGenerateSkill, _QRCODE_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _QRCODE_AVAILABLE,
    reason="qrcode library not installed",
)


@pytest.fixture
def skill():
    return QrGenerateSkill()


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestGenerate:
    def test_basic(self, skill):
        out = skill.execute(data="https://example.com")
        assert "error" not in out
        assert out["image_format"] == "png"
        assert out["data"] == "https://example.com"
        assert out["data_length"] == len("https://example.com")
        assert out["data_uri"].startswith("data:image/png;base64,")

    def test_png_signature(self, skill):
        out = skill.execute(data="hello world")
        png = base64.b64decode(out["image_base64"])
        assert png[:8] == _PNG_MAGIC
        assert out["size_bytes"] == len(png)

    @pytest.mark.parametrize("level", ["L", "M", "Q", "H"])
    def test_error_correction_levels(self, skill, level):
        out = skill.execute(data="test", error_correction=level)
        assert out["error_correction"] == level

    def test_box_size_and_border(self, skill):
        small = skill.execute(data="x", box_size=2, border=1)
        large = skill.execute(data="x", box_size=20, border=10)
        # Larger box+border must produce a bigger PNG
        assert large["size_bytes"] > small["size_bytes"]


class TestErrors:
    def test_empty_data(self, skill):
        assert "error" in skill.execute(data="")

    def test_too_long(self, skill):
        assert "error" in skill.execute(data="x" * 5000)

    def test_invalid_error_correction(self, skill):
        assert "error" in skill.execute(data="x", error_correction="Z")

    @pytest.mark.parametrize("box_size", [0, -1, 41])
    def test_invalid_box_size(self, skill, box_size):
        assert "error" in skill.execute(data="x", box_size=box_size)

    @pytest.mark.parametrize("border", [0, -1, 21])
    def test_invalid_border(self, skill, border):
        assert "error" in skill.execute(data="x", border=border)
