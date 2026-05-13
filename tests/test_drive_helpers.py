from receipt_sorter.drive import (
    ensure_child_folder,
    list_file_names,
    list_inbox_pdfs,
    move_and_rename_file,
)


class FakeExecute:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeFiles:
    def __init__(self, list_result=None, list_results=None, create_result=None):
        self.list_results = list(list_results) if list_results is not None else None
        self.list_result = list_result or {"files": []}
        self.create_result = create_result or {"id": "created-folder-id"}
        self.created_body = None
        self.updated_kwargs = None
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        self.list_kwargs = kwargs
        if self.list_results is not None:
            return FakeExecute(self.list_results.pop(0))
        return FakeExecute(self.list_result)

    def create(self, **kwargs):
        self.created_body = kwargs["body"]
        return FakeExecute(self.create_result)

    def update(self, **kwargs):
        self.updated_kwargs = kwargs
        return FakeExecute({"id": kwargs["fileId"]})


class FakeService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


def test_ensure_child_folder_reuses_existing_folder():
    files = FakeFiles(list_result={"files": [{"id": "existing-folder-id"}]})
    service = FakeService(files)

    folder_id = ensure_child_folder(service, "parent-id", "2026")

    assert folder_id == "existing-folder-id"
    assert files.created_body is None


def test_ensure_child_folder_creates_missing_folder_under_parent():
    files = FakeFiles()
    service = FakeService(files)

    folder_id = ensure_child_folder(service, "parent-id", "05-May")

    assert folder_id == "created-folder-id"
    assert files.created_body == {
        "name": "05-May",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["parent-id"],
    }


def test_move_and_rename_file_updates_name_and_parent():
    files = FakeFiles()
    service = FakeService(files)

    move_and_rename_file(
        service,
        file_id="pdf-id",
        old_parent_id="inbox-id",
        new_parent_id="month-id",
        new_name="Grab_Transport_20260315.pdf",
    )

    assert files.updated_kwargs == {
        "fileId": "pdf-id",
        "body": {"name": "Grab_Transport_20260315.pdf"},
        "addParents": "month-id",
        "removeParents": "inbox-id",
        "fields": "id, name, parents",
    }


def test_list_inbox_pdfs_fetches_all_pages():
    files = FakeFiles(
        list_results=[
            {
                "files": [{"id": "file-1", "name": "a.pdf", "mimeType": "application/pdf"}],
                "nextPageToken": "page-2",
            },
            {
                "files": [{"id": "file-2", "name": "b.pdf", "mimeType": "application/pdf"}],
            },
        ]
    )
    service = FakeService(files)

    result = list_inbox_pdfs(service, "inbox-id")

    assert result == [
        {"id": "file-1", "name": "a.pdf", "mimeType": "application/pdf"},
        {"id": "file-2", "name": "b.pdf", "mimeType": "application/pdf"},
    ]
    assert files.list_calls[0]["pageToken"] is None
    assert files.list_calls[1]["pageToken"] == "page-2"


def test_list_file_names_fetches_all_pages():
    files = FakeFiles(
        list_results=[
            {"files": [{"name": "a.pdf"}], "nextPageToken": "page-2"},
            {"files": [{"name": "b.pdf"}]},
        ]
    )
    service = FakeService(files)

    result = list_file_names(service, "folder-id")

    assert result == {"a.pdf", "b.pdf"}
    assert files.list_calls[0]["pageToken"] is None
    assert files.list_calls[1]["pageToken"] == "page-2"
