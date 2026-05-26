# Scratch Project Last Follower Title Updater

A Python script that monitors your Scratch followers and updates your project title with the most recent follower in real time. Built with [scratchattach](https://github.com/TimMcCool/scratchattach).

> **Educational project** — Created to explore APIs, caching strategies, environment variables, error handling, and server deployment with Python.

## Features

- Updates your Scratch project title every 30 seconds with your latest follower
- Smart cache system (24h) prevents re-follow abuse from spamming the title
- Handles rate limits and API errors gracefully with exponential backoff
- Auto-stops and sets `[NOT WORKING]` title when your Scratch session expires
- Runs locally or on a server 24/7
- Minimal console output — only errors, recovery events, and follower changes

## How it works

Every 30 seconds, the script checks your most recent follower. If it's a genuinely new follower (not seen in the last 24 hours), the project title updates to:

    @username | Live follower title

If someone unfollows and follows again within 24 hours, the cache ignores it. This keeps the title fair and meaningful.

## Requirements

- Python 3.9+
- A Scratch account
- [scratchattach](https://github.com/TimMcCool/scratchattach)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/KrisbelGV/scratch-last-follower-title-updater.git
    cd scratch-last-follower-title-updater
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Set up environment variables:

    ```bash
    cp .env.example .env
    ```

   Edit `.env` with your real data:
   - `SCRATCH_SESSION_ID` — See [Getting your session ID](https://github.com/TimMcCool/scratchattach/wiki/Getting-your-session-id)
   - `SCRATCH_USERNAME` — Your Scratch username (case sensitive)
   - `SCRATCH_PROJECT_ID` — The project ID to update
   - `SESSION_EXPIRY` — The expiration date of your session ID (UTC format, from browser cookies)

4. Run the script:

    ```bash
    python main.py
    ```

## Update interval

The default interval between follower checks is **30 seconds**. You can change this by editing the `INTERVAL` variable at the top of the script:

    INTERVAL = 30

A shorter interval means faster updates but more API requests. Scratch followers don't update instantly, so 30 seconds is a good balance.

## Cache system

The script maintains a `follower_cache.json` file that stores user IDs with timestamps. Followers who appear in this cache within the last 24 hours are ignored — even if they unfollow and follow again.

**Configuration options:**
- `CACHE_EXPIRY_HOURS = 24` — How long a follower stays in the cache
- `MAX_CACHE_SIZE = 1000` — Maximum entries before oldest are removed

## Rate limits

Scratch allows up to **10 requests per second** to its REST API, as documented in the [Scratch REST API wiki](https://github.com/scratchfoundation/scratch-rest-api/wiki). This script makes at most 2 requests per cycle (one read followers + one write title), so with a 30-second interval you'll make only ~4 requests per minute — far below the limit.

Please keep your usage reasonable and benevolent.

## Hosting 24/7

To keep the script running permanently, see the [Hosting guide](https://github.com/TimMcCool/scratchattach/wiki/Hosting) from scratchattach. **Wispbyte** offers a free tier that works great with this project.

## License

This project is licensed under the **MIT License** — feel free to use, modify, and share it.
See [LICENSE](LICENSE) for details.

> **Note:** `scratchattach` is also MIT licensed. This project is not affiliated with Scratch or the scratchattach team.
