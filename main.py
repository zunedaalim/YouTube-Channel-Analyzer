import os
import pandas as pd
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.errors import HttpError
import re
from datetime import datetime
import time
import math

# -- API Setup (remember to plug in your own key!) --
API_KEY = "API Key"  # <<< Don't forget to update this!
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
CSV_FILE_PATH = 'youtube_channels_sample - Youtube.csv'
OUTPUT_CSV_FILE_PATH = 'youtube_channel_analysis_results.csv'

VIDEOS_TO_FETCH_PER_CHANNEL = 15
COLUMN_NAME_WITH_URLS = 'Youtube Profiles'


def extract_channel_id(profile_url, yt_client):
    # This function is a bit overgrown — handles various URL formats
    match = re.search(r'/channel/([A-Za-z0-9_-]+)', profile_url)
    if match:
        return match.group(1)

    # Handle-style input
    match = re.search(r'@([\w.-]+)', profile_url)
    if match:
        handle = match.group(1)
        print(f"Looking up channel for handle: @{handle}")
        try:
            result = yt_client.search().list(
                q=f"@{handle}", part="snippet", type="channel", maxResults=1
            ).execute()
            if result.get("items"):
                return result["items"][0]["snippet"]["channelId"]
        except HttpError as err:
            print(f"Search API error for handle @{handle}: {err}")

    # For /c/ and /user/ links, fallback to keyword search
    for regex, desc in [(r'/c/([\w-]+)', 'custom URL'), (r'/user/([\w-]+)', 'legacy username')]:
        match = re.search(regex, profile_url)
        if match:
            keyword = match.group(1)
            print(f"Trying {desc} lookup: {keyword}")
            try:
                if 'user' in desc:
                    user_resp = yt_client.channels().list(part="id", forUsername=keyword).execute()
                    if user_resp.get("items"):
                        return user_resp["items"][0]["id"]
                else:
                    search_resp = yt_client.search().list(q=keyword, part="snippet", type="channel", maxResults=1).execute()
                    if search_resp.get("items"):
                        return search_resp["items"][0]["snippet"]["channelId"]
            except HttpError as err:
                print(f"Error during {desc} search for {keyword}: {err}")

    # Last ditch: treat input as a general search query
    if not profile_url.startswith(('http', '/', '@')):
        try:
            search_resp = yt_client.search().list(q=profile_url, part="snippet", type="channel", maxResults=1).execute()
            if search_resp.get("items"):
                return search_resp["items"][0]["snippet"]["channelId"]
        except HttpError as err:
            print(f"General search failed for input '{profile_url}': {err}")

    print(f"No valid channel ID found for: {profile_url}")
    return None


def fetch_channel_info(cid, yt_client):
    try:
        resp = yt_client.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()
        if not resp.get("items"):
            print(f"No data returned for channel ID: {cid}")
            return None

        info = resp["items"][0]
        stats = info.get("statistics", {})
        details = info.get("contentDetails", {})
        snippet = info.get("snippet", {})

        # This avoids crashing on private subscriber counts
        sub_count = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 'Hidden'

        return {
            "channel_name": snippet.get("title"),
            "channel_id": cid,
            "subscribers": sub_count,
            "total_views": int(stats.get("viewCount", 0)),
            "total_videos": int(stats.get("videoCount", 0)),
            "uploads_playlist_id": details.get("relatedPlaylists", {}).get("uploads"),
            "description": snippet.get("description"),
            "published_at": snippet.get("publishedAt"),
        }
    except HttpError as err:
        print(f"API Error while fetching channel info: {err}")
        return None


def fetch_videos_from_playlist(playlist_id, yt_client, limit=VIDEOS_TO_FETCH_PER_CHANNEL):
    all_videos = []
    ids_to_lookup = []
    page_token = None

    while len(ids_to_lookup) < limit:
        try:
            resp = yt_client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, limit - len(ids_to_lookup)),
                pageToken=page_token
            ).execute()

            for entry in resp.get("items", []):
                video_id = entry.get("contentDetails", {}).get("videoId")
                pub_date = entry.get("contentDetails", {}).get("videoPublishedAt") or \
                           entry.get("snippet", {}).get("publishedAt")

                if video_id and pub_date:
                    try:
                        dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        all_videos.append({"id": video_id, "published_at": dt})
                        ids_to_lookup.append(video_id)
                    except Exception:
                        print(f"Couldn't parse date for video: {video_id}")

            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        except HttpError as err:
            print(f"Error retrieving playlist: {err}")
            break

    if not ids_to_lookup:
        return [], {}, 0.0, []

    print(f"Retrieving stats for {len(ids_to_lookup)} videos...")
    video_stats = retrieve_video_stats(ids_to_lookup, yt_client)

    # Enrich data and calculate avg likes
    total_likes = 0
    titles = []
    for v in all_videos:
        stats = video_stats.get(v["id"], {})
        v.update(stats)
        titles.append(stats.get("title", "N/A"))
        total_likes += stats.get("likes", 0)

    avg_likes = total_likes / len(all_videos) if all_videos else 0
    all_videos.sort(key=lambda x: x["published_at"])

    return all_videos, video_stats, avg_likes, titles


def retrieve_video_stats(video_ids, yt_client):
    stats_map = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            response = yt_client.videos().list(
                part="statistics,snippet",
                id=",".join(batch)
            ).execute()

            for item in response.get("items", []):
                vid = item["id"]
                stat = item.get("statistics", {})
                snip = item.get("snippet", {})
                stats_map[vid] = {
                    "likes": int(stat.get("likeCount", 0)),
                    "views": int(stat.get("viewCount", 0)),
                    "comments": int(stat.get("commentCount", 0)),
                    "title": snip.get("title", "Untitled")
                }
        except Exception as e:
            print(f"Error during batch video stat fetch: {e}")
            for vid in batch:
                stats_map[vid] = {"likes": 0, "views": 0, "comments": 0, "title": "N/A"}

    return stats_map


def estimate_upload_rate(videos):
    if len(videos) < 2:
        return "Too few videos"

    delta_days = (videos[-1]["published_at"] - videos[0]["published_at"]).days
    if delta_days <= 0:
        return "Uploads too close together"

    freq = (len(videos) - 1) / delta_days * 7  # to weekly estimate
    return f"{freq:.2f} per week"


def compute_engagement(avg_likes, subs):
    if isinstance(subs, str) or not subs:
        return 0.0
    return round((avg_likes / subs) * 100, 2)


def main():
    if API_KEY == "API Key":
        print("Reminder: Plug in your actual API Key above!")
        return

    try:
        yt = googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)
    except Exception as err:
        print(f"API client setup failed: {err}")
        return

    try:
        df = pd.read_csv(CSV_FILE_PATH)
        profiles = df[COLUMN_NAME_WITH_URLS].dropna().unique()
    except Exception as err:
        print(f"Error loading input CSV: {err}")
        return

    results = []
    seen_channels = set()

    for profile in profiles:
        print(f"\n>> Checking: {profile}")
        cid = extract_channel_id(profile, yt)

        if not cid or cid in seen_channels:
            print("Skipping duplicate or unresolved profile.")
            continue
        seen_channels.add(cid)

        info = fetch_channel_info(cid, yt)
        if not info:
            results.append({
                "Input URL": profile,
                "Channel Name": "N/A",
                "Subscribers": "N/A",
                "Total Views": "N/A",
                "Avg. Likes": "N/A",
                "Engagement Rate": 0.0,
                "Upload Frequency": "N/A",
                "Video Titles": [],
                "Error": "Channel info not found"
            })
            continue

        vids, _, avg_likes, titles = fetch_videos_from_playlist(info.get("uploads_playlist_id", ""), yt)
        freq = estimate_upload_rate(vids) if vids else "N/A"
        engage = compute_engagement(avg_likes, info["subscribers"])

        results.append({
            "Input URL": profile,
            "Channel Name": info["channel_name"],
            "Subscribers": info["subscribers"],
            "Total Views": info["total_views"],
            "Avg. Likes": round(avg_likes, 2),
            "Engagement Rate": engage,
            "Upload Frequency": freq,
            "Video Titles": titles,
            "Channel ID": info["channel_id"],
            "Total Videos": info.get("total_videos", "N/A"),
            "Error": None
        })

        time.sleep(0.5)  # trying to avoid hitting API rate limits

    output_df = pd.DataFrame(results)
    output_df.to_csv(OUTPUT_CSV_FILE_PATH, index=False, encoding='utf-8-sig')
    print(f"\nDone. Results saved to {OUTPUT_CSV_FILE_PATH}")


if __name__ == "__main__":
    main()
