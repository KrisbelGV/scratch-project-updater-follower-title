import os
import time
import sys
import json
import warnings
from datetime import datetime, timezone, timedelta
import scratchattach as scratch3
from dotenv import load_dotenv
from scratchattach.utils.exceptions import (
    RateLimitedError, Response429, FetchError,
    Unauthenticated, Unauthorized, LoginFailure, XTokenError
)

warnings.filterwarnings("ignore", category=scratch3.LoginDataWarning)

load_dotenv()

SESSION_ID = os.environ.get("SCRATCH_SESSION_ID")
USERNAME = os.environ.get("SCRATCH_USERNAME")
PROJECT_ID = os.environ.get("SCRATCH_PROJECT_ID")
SESSION_EXPIRY = os.environ.get("SESSION_EXPIRY")

if not all([SESSION_ID, USERNAME, PROJECT_ID, SESSION_EXPIRY]):
    raise ValueError(
        "Environment variables are missing. Make sure the .env file exists "
        "and contains SCRATCH_SESSION_ID, SCRATCH_USERNAME, SCRATCH_PROJECT_ID and SESSION_EXPIRY"
    )

PROJECT_ID = int(PROJECT_ID)

INTERVAL = 30
MAX_RETRY_WAIT = 600
MAX_AUTH_FAILS = 3
CACHE_EXPIRY_HOURS = 24
CACHE_FILE = "follower_cache.json"
MAX_CACHE_SIZE = 1000

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def clean_expired_cache(cache):
    now = datetime.now(timezone.utc)
    expiry_delta = timedelta(hours=CACHE_EXPIRY_HOURS)
    
    cleaned_cache = {}
    for user_id, timestamp_str in cache.items():
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if now - timestamp < expiry_delta:
                cleaned_cache[user_id] = timestamp_str
        except (ValueError, TypeError):
            continue
    
    if len(cleaned_cache) > MAX_CACHE_SIZE:
        sorted_entries = sorted(
            cleaned_cache.items(),
            key=lambda x: x[1],
            reverse=True
        )
        cleaned_cache = dict(sorted_entries[:MAX_CACHE_SIZE])
    
    return cleaned_cache

def is_new_follower(user_id, cache):
    if user_id not in cache:
        return True
    
    try:
        timestamp = datetime.fromisoformat(cache[user_id])
        expiry_delta = timedelta(hours=CACHE_EXPIRY_HOURS)
        if datetime.now(timezone.utc) - timestamp >= expiry_delta:
            return True
    except (ValueError, TypeError):
        return True
    
    return False

def log_fatal(message):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open("fatal_error.log", "w") as f:
        f.write(f"[{timestamp}] {message}\n")

def parse_expiry(expiry_str):
    return datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

expiry_date = parse_expiry(SESSION_EXPIRY)
print(f"Session expires on: {expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"Script will auto-stop 1 hour before expiry.")

print(f"Connecting to project {PROJECT_ID} as {USERNAME}...")
session = scratch3.login_by_id(SESSION_ID, username=USERNAME)
project = session.connect_project(PROJECT_ID)
user = session.connect_user(USERNAME)

print(f"Monitoring followers of user '{USERNAME}'...")
print(f"Interval between checks: {INTERVAL} seconds")
print(f"Cache expiry: {CACHE_EXPIRY_HOURS} hours")
print("Server running. Waiting for follower changes...\n")

retry_count = 0
auth_fail_count = 0
was_in_error = False
total_wait = 0
last_follower = ""
follower_cache = load_cache()

def handle_retryable_error(message, wait_time):
    global was_in_error, total_wait
    print(message)
    was_in_error = True
    total_wait += wait_time
    time.sleep(wait_time)

while True:
    now = datetime.now(timezone.utc)
    margin = timedelta(hours=1)
    if now >= (expiry_date - margin):
        message = "Session ID expired or will expire within 1 hour. Shutting down."
        print(message)
        
        try:
            not_working_title = f"[NOT WORKING] @{last_follower} | Live follower title"
            project.set_title(not_working_title)
            print(f"Changed title to: {not_working_title}")
        except Exception as e:
            print(f"Could not update title before shutdown: {e}")
        
        log_fatal(message)
        sys.exit(0)
    
    try:
        follower_cache = clean_expired_cache(follower_cache)
        
        followers = user.followers(limit=1, offset=0)
        
        if followers:
            current_follower = followers[0]
            current_follower_name = current_follower.username
            current_follower_id = str(current_follower.id)
            
            if is_new_follower(current_follower_id, follower_cache):
                if current_follower_name != last_follower:
                    last_follower = current_follower_name
                    new_title = f"@{last_follower} | Live follower title"
                    
                    if project.title != new_title:
                        project.set_title(new_title)
                
                follower_cache[current_follower_id] = datetime.now(timezone.utc).isoformat()
                save_cache(follower_cache)
            
        if was_in_error:
            recovery_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            recovery_message = f"Recovered after {total_wait}s of downtime at {recovery_time}."
            print(recovery_message)
            
            with open("recovery.log", "a") as f:
                f.write(f"[{recovery_time}] {recovery_message}\n")
            
            was_in_error = False
            total_wait = 0
        
        retry_count = 0
        auth_fail_count = 0
        
    except (Unauthenticated, LoginFailure, XTokenError) as e:
        message = f"FATAL: Session expired or invalid: {e}"
        print(message)
        log_fatal(message)
        sys.exit(1)
        
    except Unauthorized as e:
        auth_fail_count += 1
        print(f"Unauthorized ({auth_fail_count}/{MAX_AUTH_FAILS}): {e}")
        
        if auth_fail_count >= MAX_AUTH_FAILS:
            message = "FATAL: Too many authentication failures. Stopping script."
            print(message)
            log_fatal(message)
            sys.exit(1)
        
        handle_retryable_error("Waiting 5 minutes before retry...", 300)
        continue
        
    except RateLimitedError:
        retry_count += 1
        wait_time = min(2 ** retry_count, MAX_RETRY_WAIT)
        handle_retryable_error(f"Rate limit (scratchattach). Waiting {wait_time}s...", wait_time)
        continue
        
    except Response429:
        retry_count += 1
        wait_time = min(2 ** retry_count, MAX_RETRY_WAIT)
        handle_retryable_error(f"Error 429 from Scratch API. Waiting {wait_time}s...", wait_time)
        continue
        
    except FetchError:
        retry_count += 1
        wait_time = min(2 ** retry_count, MAX_RETRY_WAIT)
        handle_retryable_error(f"Scratch API error (FetchError). Waiting {wait_time}s...", wait_time)
        continue
        
    except Exception as e:
        handle_retryable_error(f"Error: {e}. Trying again in {INTERVAL} seconds...", INTERVAL)
        retry_count = 0
    
    time.sleep(INTERVAL)