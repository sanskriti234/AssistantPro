
from app.core.config import get_settings
from google_auth_oauthlib.flow import InstalledAppFlow

settings = get_settings()

if not (
    settings.google_oauth_client_id
    and settings.google_oauth_client_secret
):
    raise RuntimeError("Google OAuth client credentials are missing.")

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

client_config = {
    "installed": {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    scopes=SCOPES,
)

credentials = flow.run_local_server(
    host="localhost",
    port=0,
    access_type="offline",
    prompt="consent",
)

if not credentials.refresh_token:
    raise RuntimeError(
        "Google did not return a refresh token. "
        "Revoke the existing app authorization and retry."
    )

print("\nNew refresh token:")
print(credentials.refresh_token)
print("\nCopy this token into your backend .env file.")