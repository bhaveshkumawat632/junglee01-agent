#!/usr/bin/env python3
import argparse, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES=["https://www.googleapis.com/auth/youtube.upload"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--file",required=True)
    ap.add_argument("--title",required=True)
    ap.add_argument("--description",default="")
    ap.add_argument("--tags",default="")
    ap.add_argument("--privacy",choices=["private","unlisted","public"],default="public")
    ap.add_argument("--language")
    ap.add_argument("--category",default="22")
    args=ap.parse_args()

    required=["YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN"]
    missing=[k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit("Missing YouTube OAuth configuration: "+", ".join(missing))

    creds=Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    yt=build("youtube","v3",credentials=creds,cache_discovery=False)
    snippet={
        "title":args.title,
        "description":args.description,
        "categoryId":args.category,
    }
    if args.tags:
        snippet["tags"]=[x.strip() for x in args.tags.split(",") if x.strip()]
    if args.language:
        snippet["defaultLanguage"]=args.language
        snippet["defaultAudioLanguage"]=args.language

    request=yt.videos().insert(
        part="snippet,status",
        body={"snippet":snippet,"status":{"privacyStatus":args.privacy,"selfDeclaredMadeForKids":False}},
        media_body=MediaFileUpload(args.file,chunksize=8*1024*1024,resumable=True),
    )
    response=None
    while response is None:
        status,response=request.next_chunk()
        if status:
            print(f"upload={int(status.progress()*100)}%")
    print("VIDEO_ID="+response["id"])
    print("URL=https://youtu.be/"+response["id"])
if __name__=="__main__":
    main()
