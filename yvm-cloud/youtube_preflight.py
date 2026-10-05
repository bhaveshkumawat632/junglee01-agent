#!/usr/bin/env python3
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES=["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube.readonly"]

def main():
    required=["YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN"]
    missing=[k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit("Missing: "+", ".join(missing))
    creds=Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    yt=build("youtube","v3",credentials=creds,cache_discovery=False)
    data=yt.channels().list(part="snippet,status",mine=True).execute()
    items=data.get("items",[])
    if not items:
        raise SystemExit("No YouTube channel returned for this OAuth account")
    ch=items[0]
    print("YOUTUBE_AUTH=PASS")
    print("CHANNEL_ID="+ch["id"])
    print("CHANNEL_TITLE="+ch["snippet"].get("title",""))
    print("PRIVACY="+ch.get("status",{}).get("privacyStatus",""))

if __name__=="__main__":
    main()
