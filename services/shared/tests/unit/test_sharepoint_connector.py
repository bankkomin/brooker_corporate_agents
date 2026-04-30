def test_sync_result_fields():
    from services.shared.sharepoint_connector import SyncResult
    r = SyncResult(folder_path="/Finance", dept_id="finance", files_checked=10, files_new=3, files_updated=1, files_skipped=6)
    assert r.files_checked == 10
    assert r.files_new == 3
    assert r.errors == []
