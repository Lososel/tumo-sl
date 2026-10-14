#!/usr/bin/env python3
"""Download the master student workbook from Google Drive with a service-account key.

Same approach as the onboarding app (tumo-onb-app): the key signs its own OAuth token, so
only the Google Drive API needs to be enabled in the key's Cloud project.

Usage (key in $GOOGLE_SERVICE_ACCOUNT_JSON):
  python3 tools/fetch_sheet.py <file id> <output path>
"""
import json
import os
import sys

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def load_key(raw):
    """Parse the pasted key, tolerating the usual copy/paste damage (as tumo-onb-app does)."""
    info = json.loads(raw.strip(), strict=False)
    if isinstance(info, str):  # JSON pasted as a quoted string
        info = json.loads(info, strict=False)
    if not isinstance(info, dict) or info.get("type") != "service_account":
        raise SystemExit("GOOGLE_SERVICE_ACCOUNT_JSON is not a service-account key")
    info["private_key"] = str(info.get("private_key", "")).replace("\\n", "\n")
    return info


def main():
    file_id, out_path = sys.argv[1], sys.argv[2]
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        load_key(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]), scopes=[DRIVE_SCOPE])
    session = AuthorizedSession(creds)
    meta = session.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                       params={"fields": "name,mimeType,modifiedTime", "supportsAllDrives": "true"})
    if meta.status_code != 200:
        raise SystemExit(f"Drive API {meta.status_code}: {meta.text[:500]}\n"
                         f"Is the file shared with {creds.service_account_email}?")
    info = meta.json()
    if info["mimeType"] == "application/vnd.google-apps.spreadsheet":  # native Google Sheet
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
        params = {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    else:  # .xlsx stored in Drive
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        params = {"alt": "media", "supportsAllDrives": "true"}
    resp = session.get(url, params=params)
    if resp.status_code != 200:
        raise SystemExit(f"Download failed: Drive API {resp.status_code}: {resp.text[:500]}")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"Downloaded '{info['name']}' (modified {info['modifiedTime']}), {len(resp.content)} bytes")


if __name__ == "__main__":
    main()
