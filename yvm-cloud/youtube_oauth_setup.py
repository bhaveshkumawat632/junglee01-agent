#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES=["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube.readonly"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--client-secret",required=True,help="OAuth Desktop App JSON downloaded from Google Cloud")
    ap.add_argument("--output",default=".yvm-youtube-token.json")
    a=ap.parse_args()

    flow=InstalledAppFlow.from_client_secrets_file(a.client_secret,SCOPES)
    creds=flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message="Open this URL in your browser:\n{url}",
        success_message="YouTube authorization completed. You can close this tab.",
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    data={
      "client_id":creds.client_id,
      "client_secret":creds.client_secret,
      "refresh_token":creds.refresh_token,
      "token_uri":creds.token_uri,
      "scopes":list(creds.scopes or SCOPES),
    }
    Path(a.output).write_text(json.dumps(data,indent=2))
    print("OAUTH_STATUS=PASS")
    print("TOKEN_FILE="+a.output)
    print("Add these three values to GitHub Actions Secrets:")
    print("YOUTUBE_CLIENT_ID="+str(creds.client_id))
    print("YOUTUBE_CLIENT_SECRET="+str(creds.client_secret))
    print("YOUTUBE_REFRESH_TOKEN="+str(creds.refresh_token))
    print("Do not commit or share the token file.")

if __name__=="__main__":
    main()
