"""
One-time setup script: obtains a Google OAuth 2.0 refresh token for the
institutional Google account CoreSight should create registration forms
under.

Run this ONCE, locally, from a machine with a browser, logged into the
Google account CoreSight should use (e.g. a registrar/admin account - not
an individual CoreSight admin's personal login, since CoreSight's own
admin auth is separate from this Google identity - see backend/README.md
"Google Cloud setup").

Usage:
    cd backend
    python scripts/get_google_refresh_token.py \
        --client-id YOUR_CLIENT_ID \
        --client-secret YOUR_CLIENT_SECRET

This opens a local browser window for the Google consent screen, then
prints the resulting refresh token to the terminal. Copy it into
GOOGLE_OAUTH_REFRESH_TOKEN in backend/.env - do not commit it, do not paste
it anywhere else, and do not log it (this script only ever prints it to
your own terminal, once).
"""

import argparse
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.services.google_forms_service import FORMS_SCOPES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--port", type=int, default=8765, help="Local port for the OAuth redirect (default 8765)")
    args = parser.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://localhost:{args.port}/"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=FORMS_SCOPES)
    # access_type=offline + prompt=consent guarantee a refresh_token is
    # returned even if this Google account has authorized this app before.
    credentials = flow.run_local_server(
        port=args.port, access_type="offline", prompt="consent"
    )

    if not credentials.refresh_token:
        print(
            "No refresh token was returned. This usually means the account "
            "already granted consent previously without offline access. Try "
            "again after revoking CoreSight's access at "
            "https://myaccount.google.com/permissions, then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nSuccess. Add this to backend/.env:\n")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}\n")


if __name__ == "__main__":
    main()
