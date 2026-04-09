import os
import re
import logging
import requests

logger = logging.getLogger("video-indexer")


def _extract_video_id(url: str) -> str:
    """Extracts YouTube video ID from any YouTube URL format."""
    patterns = [
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


class YouTubeTranscriptService:
    """
    Fetches video transcript and metadata directly from YouTube Data API v3.
    No video download needed — fast, reliable, works from any server.
    """

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("Missing required environment variable: YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def get_video_metadata(self, video_id: str) -> dict:
        """Fetches video title, description, tags, duration."""
        url = f"{self.base_url}/videos"
        params = {
            "key": self.api_key,
            "id": video_id,
            "part": "snippet,contentDetails,statistics",
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"YouTube API metadata fetch failed: {response.text}")

        items = response.json().get("items", [])
        if not items:
            raise Exception(f"No video found for ID: {video_id}")

        snippet = items[0].get("snippet", {})
        content = items[0].get("contentDetails", {})

        return {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "duration": content.get("duration", ""),
            "channel": snippet.get("channelTitle", ""),
            "platform": "youtube",
        }

    def extract_data(self, video_url: str) -> dict:
        """
        Main entry point — extracts all available text data from a YouTube video.
        Uses title + description + tags as the transcript for compliance auditing.
        """
        video_id = _extract_video_id(video_url)
        logger.info(f"Extracting data for video ID: {video_id}")

        metadata = self.get_video_metadata(video_id)

        transcript_parts = []

        if metadata.get("title"):
            transcript_parts.append(f"Title: {metadata['title']}")

        if metadata.get("description"):
            transcript_parts.append(f"Description: {metadata['description']}")

        if metadata.get("tags"):
            transcript_parts.append(f"Tags: {', '.join(metadata['tags'])}")

        transcript = "\n\n".join(transcript_parts)

        logger.info(f"Extracted {len(transcript)} chars of text for video {video_id}")

        return {
            "transcript": transcript,
            "ocr_text": [],
            "video_metadata": metadata,
        }


# ── Keep VideoIndexerService for the /debug/vi-test endpoint ─────────────────
from azure.identity import DefaultAzureCredential


class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "shubh-llm-indexer-project")
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure Token: {e}")
            raise

    def get_account_token(self, arm_access_token):
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")