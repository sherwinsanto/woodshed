import urllib.error
import urllib.request
import uuid

import pytest

from app.config import Settings
from app.storage import Storage, original_key, song_prefix, stem_key

SONG_BYTES = b"pretend this is an mp3 " * 500


def http(url: str, method: str = "GET", data: bytes | None = None, headers=None):
    """Send a request the way a browser would, straight to storage."""
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    return urllib.request.urlopen(request)


def upload(storage: Storage, key: str, content_type: str = "audio/mpeg") -> None:
    url = storage.presigned_upload_url(key, content_type)
    http(url, "PUT", SONG_BYTES, {"Content-Type": content_type})


# Unit tests: no storage server needed


def test_keys_group_everything_for_a_song_under_one_prefix() -> None:
    song_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert song_prefix(song_id) == f"songs/{song_id}/"
    assert original_key(song_id, ".MP3") == f"songs/{song_id}/original.mp3"
    assert stem_key(song_id, "vocals") == f"songs/{song_id}/stems/vocals.mp3"


@pytest.mark.parametrize("prefix", ["", "/", "songs"])
def test_delete_prefix_refuses_prefixes_that_could_match_everything(prefix: str) -> None:
    with pytest.raises(ValueError, match="refusing"):
        Storage(Settings()).delete_prefix(prefix)


def test_presigned_urls_use_the_public_address() -> None:
    settings = Settings(
        s3_endpoint_url="http://storage:9000", s3_public_endpoint_url="http://localhost:9000"
    )
    url = Storage(settings).presigned_upload_url("songs/x/original.mp3", "audio/mpeg")
    assert url.startswith("http://localhost:9000/")


# Integration tests: run against the real local storage server


def test_browser_can_upload_then_download(storage: Storage) -> None:
    key = original_key(uuid.uuid4(), "mp3")
    upload(storage, key)

    assert storage.object_size(key) == len(SONG_BYTES)
    assert http(storage.presigned_download_url(key)).read() == SONG_BYTES


def test_upload_with_a_different_content_type_is_rejected(storage: Storage) -> None:
    url = storage.presigned_upload_url(original_key(uuid.uuid4(), "mp3"), "audio/mpeg")
    with pytest.raises(urllib.error.HTTPError) as err:
        http(url, "PUT", SONG_BYTES, {"Content-Type": "text/html"})
    assert err.value.code == 403


def test_object_size_is_none_when_nothing_was_uploaded(storage: Storage) -> None:
    assert storage.object_size(original_key(uuid.uuid4(), "mp3")) is None


def test_download_name_makes_the_browser_save_the_file(storage: Storage) -> None:
    key = stem_key(uuid.uuid4(), "vocals")
    upload(storage, key)
    response = http(storage.presigned_download_url(key, download_name="My Song - vocals.mp3"))
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="My Song - vocals.mp3"'
    )


def test_cors_allows_our_frontend_only(storage: Storage) -> None:
    url = storage.presigned_upload_url(original_key(uuid.uuid4(), "mp3"), "audio/mpeg")
    preflight = {"Access-Control-Request-Method": "PUT"}

    allowed = http(url, "OPTIONS", headers={"Origin": "http://localhost:5173", **preflight})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"

    try:
        other = http(url, "OPTIONS", headers={"Origin": "https://evil.example", **preflight})
        assert other.headers.get("Access-Control-Allow-Origin") is None
    except urllib.error.HTTPError as err:
        assert err.code == 403


def test_delete_prefix_removes_only_that_song(storage: Storage) -> None:
    song, other_song = uuid.uuid4(), uuid.uuid4()
    for key in (original_key(song, "mp3"), stem_key(song, "drums"), stem_key(song, "bass")):
        upload(storage, key)
    upload(storage, original_key(other_song, "mp3"))

    assert storage.delete_prefix(song_prefix(song)) == 3
    assert storage.object_size(original_key(song, "mp3")) is None
    assert storage.object_size(original_key(other_song, "mp3")) == len(SONG_BYTES)
