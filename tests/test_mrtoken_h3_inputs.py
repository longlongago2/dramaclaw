from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from novelvideo.generators.video_generator import NewApiVideoGenerator


def generator(model="minimax-h3-r2v"):
    return NewApiVideoGenerator(api_key="test-relay-key", endpoint="http://localhost:3000/v1", model=model)


@pytest.mark.parametrize("count", [1, 4])
async def test_h3_local_reference_images_use_native_upload_without_media_relay(tmp_path, monkeypatch, count):
    path = tmp_path / "ref.png"
    Image.new("RGB", (32, 32), "blue").save(path)
    client = generator()

    async def forbidden(*args, **kwargs):
        raise AssertionError("Local H3 images must not require public media relay")

    monkeypatch.setattr(client, "_relay_frame_input", forbidden)
    metadata = {}
    paths = []
    for index in range(count):
        reference = tmp_path / f"ref-{index}.png"
        reference.write_bytes(path.read_bytes())
        paths.append(SimpleNamespace(type="image", path=str(reference), role=""))
    await client._apply_huimeng_protocol_media_inputs(metadata, mode="image_reference", image_path="", last_frame_path=None, references=paths, log=lambda message: None)
    assert len(metadata["reference_images"]) == count
    for value in metadata["reference_images"]:
        header, encoded = value.split(",", 1)
        assert header == "data:image/png;base64"
        assert base64.b64decode(encoded) == path.read_bytes()


async def test_h3_preserves_external_url_and_owned_file_id():
    client = generator()
    for value in ("https://example.test/ref.png", "file_0123456789abcdef0123456789abcdef"):
        assert await client._prepare_video_image_input(value) == value


async def test_native_seedance_keeps_existing_media_relay(tmp_path, monkeypatch):
    client = generator("doubao-seedance-2.0-mini")
    calls = []

    async def relay(value):
        calls.append(value)
        return "https://example.test/relayed.png"

    monkeypatch.setattr(client, "_relay_frame_input", relay)
    value = str(tmp_path / "ref.png")
    assert await client._prepare_video_image_input(value) == "https://example.test/relayed.png"
    assert calls == [value]


async def test_h3_rejects_oversized_local_image_before_reading(tmp_path, monkeypatch):
    path = tmp_path / "large.png"
    with path.open("wb") as image:
        image.truncate(20 * 1024 * 1024 + 1)
    client = generator()
    with pytest.raises(ValueError, match="20 MiB"):
        await client._prepare_video_image_input(str(path))


async def test_h3_rejects_unsupported_local_image_format(tmp_path):
    path = tmp_path / "ref.gif"
    Image.new("RGB", (32, 32)).save(path)
    with pytest.raises(ValueError, match="PNG, JPEG or WebP"):
        await generator()._prepare_video_image_input(str(path))
