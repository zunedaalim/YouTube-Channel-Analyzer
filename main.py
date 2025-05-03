import os
import pandas as pd
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.errors import HttpError
import re
from datetime import datetime
import time
import math

# Before running the script, get your API key using these steps:
# 1.  **API Key:**
#     *   Obtain your own YouTube Data API v3 key from the [Google Cloud Console](https://console.cloud.google.com/).
#     *   **Note:** For security reasons, the API key is not included directly in the submitted code.
API_KEY = "API Key"  # Replace with your actual API key
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
CSV_FILE_PATH = 'youtube_channels_sample - Youtube.csv'
OUTPUT_CSV_FILE_PATH = 'youtube_channel_analysis_results.csv'

VIDEOS_TO_FETCH_PER_CHANNEL = 15
COLUMN_NAME_WITH_URLS = 'Youtube Profiles'


def get_channel_id_from_input(url_or_handle, youtube):

    match = re.search(r'/channel/([A-Za-z0-9_-]+)', url_or_handle)
    if match:
        print(f"Found direct channel ID: {match.group(1)}")
        return match.group(1)

    match = re.search(r'@([A-Za-z0-9_.-]+)', url_or_handle)
    if match:
        handle = match.group(1)
        print(f"Searching for handle: @{handle}")
        try:
            search_response = youtube.search().list(
                q=f"@{handle}",
                part="snippet",
                type="channel",
                maxResults=1
            ).execute()
            if search_response.get("items"):
                channel_id = search_response["items"][0]["snippet"]["channelId"]
                print(f"Found channel ID via handle search: {channel_id}")
                return channel_id
            else:
                print(f"Could not find channel via handle search: @{handle}")
                return None
        except HttpError as e:
            print(f"API error searching for handle @{handle}: {e}")

    match = re.search(r'/c/([A-Za-z0-9_-]+)', url_or_handle)
    if match:
        custom_url_part = match.group(1)
        print(f"Searching for custom URL part: {custom_url_part}")
        try:
            search_response = youtube.search().list(
                q=custom_url_part,
                part="snippet",
                type="channel",
                maxResults=1
            ).execute()
            if search_response.get("items"):
                found_channel = search_response["items"][0]["snippet"]
                if custom_url_part.lower() in found_channel.get('title', '').lower() or \
                   custom_url_part.lower() in found_channel.get('customUrl', '').lower():
                    channel_id = found_channel["channelId"]
                    print(
                        f"Found channel ID via custom URL search: {channel_id}")
                    return channel_id
                else:
                    print(
                        f"Search result for '{custom_url_part}' doesn't seem to match. Title: {found_channel.get('title','')}")

            else:
                print(
                    f"Could not find channel via custom URL search: {custom_url_part}")

        except HttpError as e:
            print(f"API error searching for custom URL {custom_url_part}: {e}")

    match = re.search(r'/user/([A-Za-z0-9_-]+)', url_or_handle)
    if match:
        username = match.group(1)
        print(f"Trying lookup by legacy username: {username}")
        try:
            channel_response = youtube.channels().list(
                part="id",
                forUsername=username
            ).execute()
            if channel_response.get("items"):
                channel_id = channel_response["items"][0]["id"]
                print(f"Found channel ID via legacy username: {channel_id}")
                return channel_id
            else:
                print(
                    f"Could not find channel via legacy username: {username}")
        except HttpError as e:
            print(f"API error looking up legacy username {username}: {e}")

    if not url_or_handle.startswith(('http', '/', '@')):
        print(f"Attempting general search for: {url_or_handle}")
        try:
            search_response = youtube.search().list(
                q=url_or_handle,
                part="snippet",
                type="channel",
                maxResults=1
            ).execute()
            if search_response.get("items"):
                channel_id = search_response["items"][0]["snippet"]["channelId"]
                print(f"Found channel ID via general search: {channel_id}")
                return channel_id
            else:
                print(
                    f"Could not find channel via general search: {url_or_handle}")
        except HttpError as e:
            print(f"API error during general search for {url_or_handle}: {e}")

    print(f"Could not determine channel ID for input: {url_or_handle}")
    return None


def get_channel_data(channel_id, youtube):
    try:
        request = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id
        )
        response = request.execute()

        if not response.get("items"):
            print(f"Channel not found for ID: {channel_id}")
            return None

        channel_data = response["items"][0]
        stats = channel_data.get("statistics", {})
        snippet = channel_data.get("snippet", {})
        content_details = channel_data.get("contentDetails", {})

        subs_hidden = stats.get('hiddenSubscriberCount', False)
        subs_count = int(stats.get("subscriberCount", 0)
                         ) if not subs_hidden else 'Hidden'

        return {
            "channel_name": snippet.get("title"),
            "channel_id": channel_id,
            "subscribers": subs_count,
            "total_views": int(stats.get("viewCount", 0)),
            "total_videos": int(stats.get("videoCount", 0)),
            "uploads_playlist_id": content_details.get("relatedPlaylists", {}).get("uploads"),
            "description": snippet.get("description"),  # Added description
            "published_at": snippet.get("publishedAt"),
        }
    except HttpError as e:
        print(
            f"An API error occurred getting channel data for {channel_id}: {e}")
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            print("Quota Exceeded. Please wait or increase your quota.")
            raise e
        return None
    except Exception as e:
        print(
            f"An unexpected error occurred getting channel data for {channel_id}: {e}")
        return None


def get_video_details(video_ids, youtube):
    video_stats = {}
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        try:
            request = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(batch_ids)
            )
            response = request.execute()

            for item in response.get("items", []):
                video_id = item["id"]
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                likes = stats.get("likeCount")
                video_stats[video_id] = {
                    'likes': int(likes) if likes is not None else 0,
                    'views': int(stats.get("viewCount", 0)),
                    'comments': int(stats.get("commentCount", 0)),
                    'title': snippet.get('title', 'N/A')
                }
        except HttpError as e:
            print(f"An API error occurred getting video details: {e}")
            for vid in batch_ids:
                if vid not in video_stats:
                    video_stats[vid] = {'likes': 0, 'views': 0,
                                        'comments': 0, 'title': 'Error Fetching'}
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("Quota Exceeded during video detail fetch.")
                raise e
        except Exception as e:
            print(f"An unexpected error occurred getting video details: {e}")
            for vid in batch_ids:
                if vid not in video_stats:
                    video_stats[vid] = {'likes': 0, 'views': 0,
                                        'comments': 0, 'title': 'Error Fetching'}

    return video_stats


def get_recent_videos_and_stats(playlist_id, youtube, max_results=VIDEOS_TO_FETCH_PER_CHANNEL):
    video_data = []
    video_ids = []
    try:
        next_page_token = None
        while len(video_ids) < max_results:
            request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_results - len(video_ids)
                               ),
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                published_at_str = item.get("contentDetails", {}).get(
                    "videoPublishedAt")
                if not published_at_str:
                    published_at_str = item.get(
                        "snippet", {}).get("publishedAt")

                if video_id and published_at_str:
                    try:
                        published_date = datetime.fromisoformat(
                            published_at_str.replace('Z', '+00:00'))
                        video_ids.append(video_id)
                        video_data.append({
                            "id": video_id,
                            "published_at": published_date,
                        })
                    except ValueError:
                        print(
                            f"Could not parse date: {published_at_str} for video {video_id}")

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as e:
        print(f"An API error occurred getting playlist items: {e}")
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            print("Quota Exceeded during playlist fetch.")
            raise e
        if e.resp.status == 404:
            print(
                f"Uploads playlist {playlist_id} not found or access denied.")
            return [], {}, 0.0, []
    except Exception as e:
        print(f"An unexpected error occurred getting playlist items: {e}")

    if not video_ids:
        print("No video IDs found for analysis.")
        return [], {}, 0.0, []

    print(f"Fetching details for {len(video_ids)} videos...")
    video_stats = get_video_details(video_ids, youtube)
    total_likes = 0
    valid_videos_for_likes = 0
    recent_titles = []

    for video in video_data:
        stats = video_stats.get(video["id"])
        if stats:
            video.update(stats)
            total_likes += stats['likes']
            valid_videos_for_likes += 1
            recent_titles.append(stats['title'])
        else:
            video.update(
                {'likes': 0, 'views': 0, 'comments': 0, 'title': 'N/A'})
            recent_titles.append('N/A')

    avg_likes = total_likes / valid_videos_for_likes if valid_videos_for_likes > 0 else 0.0

    video_data.sort(key=lambda x: x["published_at"])

    return video_data, video_stats, avg_likes, recent_titles


def calculate_upload_frequency(video_data):
    if len(video_data) < 2:
        return "N/A (Insufficient data)"

    first_video_date = video_data[0]["published_at"]
    last_video_date = video_data[-1]["published_at"]

    time_delta = last_video_date - first_video_date
    days_span = time_delta.total_seconds() / (60 * 60 * 24)

    if days_span <= 0:
        return "N/A (Videos too close in time)"

    videos_per_day = (len(video_data) - 1) / days_span
    videos_per_week = videos_per_day * 7

    return f"{videos_per_week:.2f} videos/week"


def calculate_engagement_rate(avg_likes, subscribers):
    if isinstance(subscribers, str) or subscribers == 0 or subscribers is None:
        return 0.0

    if avg_likes is None or math.isnan(avg_likes):
        avg_likes = 0.0

    engagement_rate = (avg_likes / subscribers) * 100
    return engagement_rate


def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please replace 'YOUR_API_KEY_HERE' with your actual YouTube Data API key in the script.")
        return
    try:
        youtube = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)
        print("YouTube API client built successfully.")
    except Exception as e:
        print(f"Error building YouTube API client: {e}")
        return

    try:
        df_input = pd.read_csv(CSV_FILE_PATH)
        if COLUMN_NAME_WITH_URLS not in df_input.columns:
            print(
                f"Error: Column '{COLUMN_NAME_WITH_URLS}' not found in {CSV_FILE_PATH}")
            print(f"Available columns: {df_input.columns.tolist()}")
            return
        urls = df_input[COLUMN_NAME_WITH_URLS].dropna().unique().tolist()
        print(f"Read {len(urls)} unique YouTube profiles from {CSV_FILE_PATH}")
    except FileNotFoundError:
        print(f"Error: Input CSV file not found at {CSV_FILE_PATH}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    results = []
    processed_channels = set()

    for url in urls:
        print(f"\n--- Processing: {url} ---")
        channel_id = None
        channel_info = None
        try:
            # 1. Get Channel ID
            channel_id = get_channel_id_from_input(url, youtube)
            if not channel_id:
                print(
                    f"Skipping URL '{url}' as Channel ID could not be determined.")
                results.append({
                    'Input URL': url,
                    'Channel Name': 'Not Found',
                    'Subscribers': 'N/A',
                    'Total Views': 'N/A',
                    'Avg. Likes': 'N/A',
                    'Video Titles': [],
                    'Engagement Rate': 0.0,
                    'Upload Frequency': 'N/A',
                    'Error': 'Could not find Channel ID'
                })
                continue

            if channel_id in processed_channels:
                print(
                    f"Skipping duplicate channel ID: {channel_id} (from URL: {url})")
                continue
            processed_channels.add(channel_id)

            print(f"Fetching stats for Channel ID: {channel_id}")
            channel_info = get_channel_data(channel_id, youtube)
            if not channel_info:
                print(
                    f"Skipping channel ID {channel_id} due to error fetching data.")
                results.append({
                    'Input URL': url,
                    'Channel Name': f'Error fetching ID {channel_id}',
                    'Subscribers': 'N/A',
                    'Total Views': 'N/A',
                    'Avg. Likes': 'N/A',
                    'Video Titles': [],
                    'Engagement Rate': 0.0,
                    'Upload Frequency': 'N/A',
                    'Error': 'Failed to fetch channel data'
                })
                continue
            avg_likes = 0.0
            recent_titles = []
            upload_frequency = "N/A"
            video_data = []

            if channel_info.get("uploads_playlist_id") and channel_info.get("total_videos", 0) > 0:
                print(
                    f"Fetching recent videos from playlist: {channel_info['uploads_playlist_id']}")
                fetch_count = min(VIDEOS_TO_FETCH_PER_CHANNEL,
                                  channel_info["total_videos"])
                video_data, _, avg_likes, recent_titles = get_recent_videos_and_stats(
                    channel_info["uploads_playlist_id"], youtube, max_results=fetch_count
                )
                if video_data:
                    upload_frequency = calculate_upload_frequency(video_data)
                else:
                    print(
                        "No valid video data returned for frequency/likes calculation.")

            elif channel_info.get("total_videos", 0) == 0:
                print("Channel has no videos.")
                upload_frequency = "N/A (No videos)"

            else:
                print("Could not find uploads playlist ID.")
                upload_frequency = "N/A (Playlist missing)"

            engagement_rate = calculate_engagement_rate(
                avg_likes, channel_info["subscribers"])

            results.append({
                'Input URL': url,
                'Channel Name': channel_info["channel_name"],
                'Subscribers': channel_info["subscribers"],
                'Total Views': channel_info["total_views"],
                'Avg. Likes': round(avg_likes, 2) if isinstance(avg_likes, (int, float)) else 'N/A',
                'Video Titles': recent_titles[:VIDEOS_TO_FETCH_PER_CHANNEL],
                'Engagement Rate': round(engagement_rate, 4),
                'Upload Frequency': upload_frequency,
                'Channel ID': channel_id,
                'Total Videos': channel_info.get('total_videos', 'N/A'),
                'Error': None
            })
            print(f"Successfully processed: {channel_info['channel_name']}")

            time.sleep(0.5)

        except HttpError as e:
            print(
                f"STOPPING PROCESSING due to API Error (likely Quota Exceeded) for {url}: {e}")
            results.append({
                'Input URL': url,
                'Channel Name': f'API Error for ID {channel_id}' if channel_id else 'API Error',
                'Subscribers': 'N/A',
                'Total Views': 'N/A',
                'Avg. Likes': 'N/A',
                'Video Titles': [],
                'Engagement Rate': 0.0,
                'Upload Frequency': 'N/A',
                'Error': f'API Error: {e.resp.status} {e.reason}'
            })

            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("Quota Exceeded. Aborting further processing.")
                break

        except Exception as e:
            print(f"An unexpected error occurred processing {url}: {e}")
            results.append({
                'Input URL': url,
                'Channel Name': f'Unexpected Error for ID {channel_id}' if channel_id else 'Unexpected Error',
                'Subscribers': 'N/A',
                'Total Views': 'N/A',
                'Avg. Likes': 'N/A',
                'Video Titles': [],
                'Engagement Rate': 0.0,
                'Upload Frequency': 'N/A',
                'Error': str(e)
            })

    df_results = pd.DataFrame(results)

    output_columns = [
        'Channel Name',
        'Subscribers',
        'Total Views',
        'Avg. Likes',
        'Engagement Rate',
        'Upload Frequency',
        'Video Titles',
        'Input URL',
        'Channel ID',
        'Total Videos',
        'Error'
    ]
    df_results = df_results.reindex(columns=output_columns, fill_value='N/A')

    df_results['Engagement Rate'] = pd.to_numeric(
        df_results['Engagement Rate'], errors='coerce')
    df_results = df_results.sort_values(
        by="Engagement Rate", ascending=False, na_position='last')

    print("\n--- Analysis Results ---")
    print(df_results.to_string())

    try:
        df_results.to_csv(OUTPUT_CSV_FILE_PATH,
                          index=False, encoding='utf-8-sig')
        print(f"\nResults saved to {OUTPUT_CSV_FILE_PATH}")
    except Exception as e:
        print(f"\nError saving results to CSV: {e}")


if __name__ == "__main__":
    main()
