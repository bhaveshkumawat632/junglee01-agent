#!/usr/bin/env python3
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
RETRIABLE_STATUS = {500, 502, 503, 504}

def parse_args():
    ap=argparse.ArgumentParser(description="Upload one finished YVM video to YouTube.")
    ap.add_argument("--file",required=True)
    ap.add_argument("--title",required=True)
    ap.add_argument("--description",default="")
    ap.add_argument("--tags",default="")
    ap.add_argument("--privacy",default="private",choices=["private","unlisted","public"])
    ap.add_argument("--language",default="en")
    ap.add_argument("--category",default="27")
    ap.add_argument("--dry-run",action="store_true")
    return ap.parse_args()

def metadata(a):
    tags=[x.strip() for x in a.tags.split(",") if x.strip()]
    return {
        "snippet":{
            "title":" ".join(a.title.split())[:100],
            "description":a.description[:5000],
            "tags":tags[:100],
            "categoryId":str(a.category),
            "defaultLanguage":a.language,
        },
        "status":{
            "privacyStatus":a.privacy,
        },
    }

def credentials_from_env():
    required=["YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN"]
    missing=[k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing YouTube OAuth secrets: "+", ".join(missing))
    creds=Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds

def resumable_upload(youtube, path, body):
    media=MediaFileUpload(
        str(path),
        mimetype="video/mp4",
        chunksize=8*1024*1024,
        resumable=True,
    )
    request=youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False,
    )
    response=None
    attempt=0
    while response is None:
        try:
            status,response=request.next_chunk()
            if status:
                print(f"UPLOAD_PROGRESS={int(status.progress()*100)}",flush=True)
        except HttpError as e:
            if e.resp.status not in RETRIABLE_STATUS:
                raise
            attempt+=1
            if attempt>5:
                raise
            delay=min(60,(2**attempt)+random.random())
            print(f"RETRY_HTTP={e.resp.status} SLEEP={delay:.1f}",file=sys.stderr,flush=True)
            time.sleep(delay)
        except OSError:
            attempt+=1
            if attempt>5:
                raise
            delay=min(60,(2**attempt)+random.random())
            print(f"RETRY_IO SLEEP={delay:.1f}",file=sys.stderr,flush=True)
            time.sleep(delay)
    return response

def main():
    a=parse_args()
    path=Path(a.file)
    if not path.is_file():
        raise SystemExit(f"Video file not found: {path}")
    if path.stat().st_size < 1024:
        raise SystemExit("Video file is unexpectedly small")

    body=metadata(a)
    if a.dry_run:
        print(json.dumps({
            "status":"DRY_RUN_PASS",
            "file":str(path),
            "bytes":path.stat().st_size,
            "body":body,
        },ensure_ascii=False,indent=2))
        return

    creds=credentials_from_env()
    youtube=build("youtube","v3",credentials=creds,cache_discovery=False)
    response=resumable_upload(youtube,path,body)
    video_id=response.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload returned no video id")
    print(json.dumps({
        "status":"UPLOAD_PASS",
        "video_id":video_id,
        "watch_url":"https://www.youtube.com/watch?v="+video_id,
        "privacy":body["status"]["privacyStatus"],
        "language":a.language,
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
