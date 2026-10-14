"""
Handles the Google Form profile-photo answer, which is a Drive file
reference (fileId), not a public URL or binary data - see
registration_response_parser._extract_file_id().

This is the student's CoreSight profile photo ONLY. It is never used to
generate face embeddings - see app/services/enrollment_service.py and
face_enrollments/face_embeddings, which are populated exclusively through
the student's own dedicated phone-camera enrollment flow.

LIMITATION (see backend/README.md): not exercised against live Google
Drive or Supabase Storage in this environment (no network egress to either
service here). The download/upload calls are written against the
documented APIs (Drive `files().get_media()`, Supabase Storage
`storage.from_(bucket).upload()`) so a credentialed environment can use
this unchanged.
"""

from __future__ import annotations

import io
import logging
import uuid

from app.core.config import get_settings

logger = logging.getLogger("coresight.storage")


class ProfilePhotoError(Exception):
    """Raised on a Drive/Storage failure. Callers should treat this as best-effort and never let it block registration."""


def _build_drive_client():
    from googleapiclient.discovery import build

    from app.services.google_forms_service import _build_credentials

    return build("drive", "v3", credentials=_build_credentials(), cache_discovery=False)


def upload_profile_photo_from_drive(drive_file_id: str, student_id: uuid.UUID, *, drive_client=None, storage_client=None) -> str:
    """
    Downloads the file from Drive (server-side, using CoreSight's own
    OAuth credentials - the student never sees or needs Drive access) and
    re-uploads it to Supabase Storage. Returns the storage path to save in
    students.profile_photo_path. Raises ProfilePhotoError on any failure -
    callers must treat this step as best-effort (see registration_sync.py).
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ProfilePhotoError("Supabase Storage is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")

    try:
        from googleapiclient.http import MediaIoBaseDownload

        client = drive_client or _build_drive_client()
        metadata = client.files().get(fileId=drive_file_id, fields="mimeType,size").execute()

        mime_type = metadata.get("mimeType", "")
        if not mime_type.startswith("image/"):
            raise ProfilePhotoError(f"Uploaded profile photo is not an image (got {mime_type!r}).")
        size = int(metadata.get("size", 0) or 0)
        if size > 10 * 1024 * 1024:
            raise ProfilePhotoError("Profile photo exceeds the 10MB limit.")

        buffer = io.BytesIO()
        request = client.files().get_media(fileId=drive_file_id)
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)

        extension = mime_type.split("/")[-1] or "jpg"
        storage_path = f"student-profile-photos/{student_id}/profile.{extension}"

        client_supa = storage_client or _build_supabase_storage_client()
        client_supa.from_(settings.supabase_storage_bucket).upload(
            storage_path, buffer.read(), {"content-type": mime_type, "upsert": "true"}
        )
        return storage_path

    except ProfilePhotoError:
        raise
    except Exception as e:  # noqa: BLE001 - never leak internals; this is best-effort
        logger.error("PROFILE_PHOTO_UPLOAD_FAILED student_id=%s reason=%s", student_id, type(e).__name__)
        raise ProfilePhotoError("Could not process the profile photo.") from e


def _build_supabase_storage_client():
    from supabase import create_client

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return client.storage
