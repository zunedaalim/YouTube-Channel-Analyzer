# YouTube Channel Analyzer

A Python script to analyze YouTube channels based on their URLs, fetch key statistics, calculate engagement metrics, and rank them.

## Overview

This tool takes a list of YouTube channel URLs (or handles) from a CSV file, uses the YouTube Data API v3 to gather information about each channel and its recent videos, calculates metrics like average likes and upload frequency, and outputs the results into a new CSV file, sorted by engagement rate.

## Features

- Fetches core channel statistics:
  - Subscribers (Handles hidden counts)
  - Total Views
  - Total Video Count
- Analyzes recent videos (configurable number, default 15) to calculate:
  - Average Likes per video
- Extracts recent Video Titles.
- Calculates metrics:
  - **Engagement Rate:** (Average Likes on Recent Videos / Subscribers) \* 100
  - **Upload Frequency:** Videos uploaded per week (based on the analyzed recent videos)
- Handles various YouTube URL formats (`/channel/`, `/c/`, `/@handle`, `/user/`) and attempts general search for names.
- Outputs results to a CSV file, sorted by Engagement Rate (descending).
- Includes basic error handling for API issues and channel lookup failures.

## Prerequisites

- **Python:** Version 3.7 or higher recommended.
- **Pip:** Python package installer (usually comes with Python).
- **Git:** For cloning the repository (optional, if downloading).
- **YouTube Data API v3 Key:** You **MUST** obtain an API key from the Google Cloud Console.
  1.  Go to [Google Cloud Console](https://console.cloud.google.com/).
  2.  Create a project or select an existing one.
  3.  Enable the "YouTube Data API v3" service.
  4.  Create an API key under "Credentials".
  5.  **Keep your API key secure!**
- **Input CSV File:** A CSV file containing the YouTube channel URLs/handles.

## Setup

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/zunedaalim/YouTube-Channel-Analyzer.git
    cd YouTube-Channel-Analyzer
    ```

    _(Or download the files manually)_

2.  **Install Dependencies:**
    ```bash
    pip install --upgrade google-api-python-client google-auth-oauthlib google-auth-httplib2 pandas
    ```
    _(Alternatively, if a `requirements.txt` file is provided: `pip install -r requirements.txt`)_

## Configuration

Before running the script, configure the following variables within the Python file (e.g., `youtube_analyzer.py`):

1.  **API Key (CRITICAL):**

    - Find the line `API_KEY = "YOUR_API_KEY_HERE"`
    - Replace `"YOUR_API_KEY_HERE"` with your actual YouTube Data API key.
    - **SECURITY WARNING:** Do **NOT** commit your API key directly into version control (like Git/GitHub) if the repository is public or shared. Consider using environment variables or a separate configuration file (added to `.gitignore`) for better security in real-world applications.

2.  **Input/Output Files:**

    - `CSV_FILE_PATH`: Set the path to your input CSV file (default: `'youtube_channels_sample - Youtube.csv'`).
    - `OUTPUT_CSV_FILE_PATH`: Set the desired path for the output results (default: `'youtube_channel_analysis_results.csv'`).

3.  **Analysis Parameters:**
    - `VIDEOS_TO_FETCH_PER_CHANNEL`: Number of recent videos to analyze for likes and frequency (default: `15`).
    - `COLUMN_NAME_WITH_URLS`: The exact name of the column in your input CSV that contains the YouTube URLs/handles (default: `'Youtube Profiles'`).

## Usage

1.  Ensure your input CSV file (e.g., `youtube_channels_sample - Youtube.csv`) is correctly placed and named according to the `CSV_FILE_PATH` setting.
2.  Make sure the column containing the URLs matches the `COLUMN_NAME_WITH_URLS` setting.
3.  Run the script from your terminal:

    ```bash
    python youtube_analyzer.py
    ```

    _(Replace `youtube_analyzer.py` with the actual name of your script file if different)_

4.  The script will print progress updates to the console and indicate any errors encountered.
5.  Upon completion, the results will be saved to the specified `OUTPUT_CSV_FILE_PATH` (e.g., `youtube_channel_analysis_results.csv`).

## Input File Format

- A CSV file (e.g., `youtube_channels_sample - Youtube.csv`).
- Must contain a column with the name specified in `COLUMN_NAME_WITH_URLS` (default: `Youtube Profiles`).
- This column should contain one YouTube channel identifier per row. Examples:
  - Full URL: `https://www.youtube.com/channel/UCXXXXXX`
  - Custom URL: `https://www.youtube.com/c/ChannelName`
  - Handle URL: `https://www.youtube.com/@HandleName`
  - Legacy User URL: `https://www.youtube.com/user/UserName`
  - Handle only: `@HandleName`
  - Channel Name only: `Example Channel Name` (less reliable, relies on search)

## Output File Format

- A CSV file (e.g., `youtube_channel_analysis_results.csv`).
- Contains the analysis results with the following columns:
  - `Channel Name`: The official name of the channel.
  - `Subscribers`: Number of subscribers ('Hidden' if not public).
  - `Total Views`: Total views across all channel videos.
  - `Avg. Likes`: Average likes calculated from the most recent videos analyzed.
  - `Engagement Rate`: Calculated as `(Avg. Likes / Subscribers) * 100`. Returns 0 if subscribers are hidden or zero.
  - `Upload Frequency`: Estimated videos per week based on recent uploads.
  - `Video Titles`: A list of titles from the recently analyzed videos.
  - `Input URL`: The original URL/identifier provided in the input file.
  - `Channel ID`: The unique YouTube channel ID (UC...).
  - `Total Videos`: Total number of public videos on the channel.
  - `Error`: Contains details if an error occurred during processing for that specific channel (e.g., 'Could not find Channel ID', 'API Error', 'Quota Exceeded').
- The data is sorted by `Engagement Rate` in descending order (highest first).

## Important Notes

- **API Quotas:** The YouTube Data API v3 has daily usage quotas. Processing a large number of channels may exhaust your quota, causing the script to fail with quota errors. Check your Google Cloud Console for quota details.
- **Rate Limiting:** While the script includes a small delay, very rapid execution or processing many channels quickly could potentially hit API rate limits.
- **Channel ID Resolution:** The script attempts to find the correct Channel ID from various inputs, but unusual URL structures or ambiguous channel names might lead to lookup failures (indicated in the 'Error' column).
- **Data Accuracy:** All data is fetched directly from the YouTube API at the time of script execution. Likes, views, and subscriber counts can fluctuate. Average likes and frequency are based _only_ on the sample of recent videos fetched.
