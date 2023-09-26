import importlib
from fastapi.testclient import TestClient

main = importlib.import_module("src.main", package="src")
client = TestClient(main.app)


def test_missing_url_returns_422():
    response = client.get("/")
    assert response.status_code == 422


def test_youtube_url_returns_summary_with_expected_words():
    response = client.get("/?url=https://www.youtube.com/watch?v=h7gf5M04hdg")
    assert response.status_code == 200
    json = response.json()
    lowered_summary = json["summary"].lower()
    assert "temple" in lowered_summary
    assert "terry" in lowered_summary


def test_apple_podcast_url_returns_summary_with_expected_words():
    response = client.get(
        "/?url=https://podcasts.apple.com/us/podcast/nikola-tesla/id899632430?i=1000553619668"
    )
    assert response.status_code == 200
    json = response.json()
    lowered_summary = json["summary"].lower()
    assert "tesla" in lowered_summary


def test_direct_download_returns_summary_with_expected_words():
    response = client.get(
        "/?url=https://dl.dropboxusercontent.com/s/pw27877dknh82tk/Audio%20-%20Martin%20Luther%20King%20-%20I%20Have%20A%20Dream.mp3?dl=1"
    )
    assert response.status_code == 200
    json = response.json()
    lowered_summary = json["summary"].lower()
    assert "martin luther king" in lowered_summary
    assert "dream" in lowered_summary
