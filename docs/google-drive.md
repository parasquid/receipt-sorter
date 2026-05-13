# Google Drive

## Folder Model

The bot operates inside configured folder IDs:

```text
Accounting/
  Inbox/
  Needs Review/
  YYYY/
    MM-Mmm/
```

Only `Accounting/` and `Inbox/` must exist before startup. Year/month folders and `Needs Review/` are created when needed.

## Folder IDs

Use folder IDs from Drive URLs:

```text
https://drive.google.com/drive/folders/<FOLDER_ID>
```

Configure:

```bash
DRIVE_ACCOUNTING_FOLDER_ID=
DRIVE_INBOX_FOLDER_ID=
```

## Scope

The v0/v1 local setup uses:

```text
https://www.googleapis.com/auth/drive
```

The broad Drive scope is used because the bot must read, rename, move, and create files in folders the user manually creates. For a public hosted service, this would need a narrower authorization and account model.

## Application Default Credentials

Runtime uses Google Application Default Credentials. The expected local auth command is:

```bash
gcloud auth application-default login \
  --client-id-file="$HOME/.config/gcloud/receipt-sorter-oauth-client.json" \
  --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive"
```

## File Movement

Valid documents are moved from `Inbox/` to a date-based folder:

```text
Accounting/YYYY/MM-Mmm/Supplier_Category_YYYYMMDD.pdf
```

If the destination filename already exists, the bot adds a numeric suffix:

```text
Supplier_Category_YYYYMMDD-2.pdf
```

Invalid classifications are moved to:

```text
Accounting/Needs Review/
```

Transient provider or Drive failures leave the original PDF in `Inbox/` so a future run can retry it.

## Setup Helper

`setup_drive.py` can create current and previous year folders under `Accounting/`. It is optional because runtime creates the relevant month folder on demand.
