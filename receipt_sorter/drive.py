from __future__ import annotations

import asyncio
import io
import json
from typing import Any, Protocol

import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from receipt_sorter.log import log_step

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def paginated_file_list(
    service: Any,
    *,
    query: str,
    fields: str,
    page_size: int = 100,
) -> list[dict[str, str]]:
    files = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields=f"nextPageToken, {fields}",
                pageSize=page_size,
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def drive_service() -> Any:
    credentials, _ = google.auth.default(scopes=DRIVE_SCOPES)
    return build("drive", "v3", credentials=credentials)


def list_inbox_pdfs(service: Any, inbox_folder_id: str) -> list[dict[str, str]]:
    log_step("Checking Drive Inbox for PDFs...")
    query = f"'{inbox_folder_id}' in parents and mimeType = 'application/pdf' and trashed = false"
    files = paginated_file_list(service, query=query, fields="files(id, name, mimeType)")
    log_step(f"Found {len(files)} PDF(s) in Inbox.")
    return files


def list_file_names(service: Any, parent_id: str) -> set[str]:
    query = f"'{parent_id}' in parents and trashed = false"
    files = paginated_file_list(service, query=query, fields="files(name)")
    return {file["name"] for file in files if "name" in file}


def download_pdf(service: Any, file_id: str) -> bytes:
    log_step(f"Downloading PDF bytes from Drive file {file_id}...")
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    pdf_bytes = buffer.getvalue()
    log_step(f"Downloaded {len(pdf_bytes):,} bytes.")
    return pdf_bytes


def create_json_file(
    service: Any,
    parent_id: str,
    filename: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    log_step(f"Creating Drive JSON sidecar: {filename}...")
    json_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(json_bytes), mimetype="application/json", resumable=False)
    metadata = {
        "name": filename,
        "mimeType": "application/json",
        "parents": [parent_id],
    }
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, mimeType")
        .execute()
    )
    log_step(f"Created Drive JSON sidecar {created['id']}.")
    return created


def upload_pdf_to_drive_inbox(
    service: Any,
    inbox_folder_id: str,
    filename: str,
    pdf_bytes: bytes,
) -> dict[str, str]:
    log_step(f"Uploading Telegram PDF to Drive Inbox as {filename}...")
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf", resumable=False)
    metadata = {
        "name": filename,
        "mimeType": "application/pdf",
        "parents": [inbox_folder_id],
    }
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, mimeType")
        .execute()
    )
    log_step(f"Uploaded Telegram PDF to Drive file {created['id']}.")
    return created


def find_child_folder(service: Any, parent_id: str, name: str) -> str | None:
    safe_name = name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{safe_name}' and trashed = false"
    )
    response = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    files = response.get("files", [])
    return files[0]["id"] if files else None


def ensure_child_folder(service: Any, parent_id: str, name: str) -> str:
    existing_id = find_child_folder(service, parent_id, name)
    if existing_id:
        log_step(f"Using existing Drive folder: {name}/")
        return existing_id
    log_step(f"Creating Drive folder: {name}/")
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def move_and_rename_file(
    service: Any,
    file_id: str,
    old_parent_id: str,
    new_parent_id: str,
    new_name: str,
) -> None:
    log_step(f"Moving and renaming file to {new_name}...")
    service.files().update(
        fileId=file_id,
        body={"name": new_name},
        addParents=new_parent_id,
        removeParents=old_parent_id,
        fields="id, name, parents",
    ).execute()


class DriveClient(Protocol):
    async def list_inbox_pdfs(self, inbox_folder_id: str) -> list[dict[str, str]]: ...

    async def list_file_names(self, parent_id: str) -> set[str]: ...

    async def download_pdf(self, file_id: str) -> bytes: ...

    async def upload_pdf_to_drive_inbox(
        self,
        inbox_folder_id: str,
        filename: str,
        pdf_bytes: bytes,
    ) -> dict[str, str]: ...

    async def ensure_child_folder(self, parent_id: str, name: str) -> str: ...

    async def move_and_rename_file(
        self,
        file_id: str,
        old_parent_id: str,
        new_parent_id: str,
        new_name: str,
    ) -> None: ...

    async def create_json_file(
        self,
        parent_id: str,
        filename: str,
        payload: dict[str, Any],
    ) -> dict[str, str]: ...


class AsyncDriveClient:
    def __init__(self, service: Any):
        self.service = service

    async def list_inbox_pdfs(self, inbox_folder_id: str) -> list[dict[str, str]]:
        return await asyncio.to_thread(list_inbox_pdfs, self.service, inbox_folder_id)

    async def list_file_names(self, parent_id: str) -> set[str]:
        return await asyncio.to_thread(list_file_names, self.service, parent_id)

    async def download_pdf(self, file_id: str) -> bytes:
        return await asyncio.to_thread(download_pdf, self.service, file_id)

    async def upload_pdf_to_drive_inbox(
        self,
        inbox_folder_id: str,
        filename: str,
        pdf_bytes: bytes,
    ) -> dict[str, str]:
        return await asyncio.to_thread(
            upload_pdf_to_drive_inbox,
            self.service,
            inbox_folder_id,
            filename,
            pdf_bytes,
        )

    async def ensure_child_folder(self, parent_id: str, name: str) -> str:
        return await asyncio.to_thread(ensure_child_folder, self.service, parent_id, name)

    async def move_and_rename_file(
        self,
        file_id: str,
        old_parent_id: str,
        new_parent_id: str,
        new_name: str,
    ) -> None:
        await asyncio.to_thread(
            move_and_rename_file,
            self.service,
            file_id,
            old_parent_id,
            new_parent_id,
            new_name,
        )

    async def create_json_file(
        self,
        parent_id: str,
        filename: str,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        return await asyncio.to_thread(create_json_file, self.service, parent_id, filename, payload)
