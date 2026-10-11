import io
import zipfile
from types import SimpleNamespace

import pytest
from bson import ObjectId
from PIL import Image

import material_service as materials


class FakeResources:
    def __init__(self, resource):
        self.resource = resource
        self.updates = []

    def find_one(self, query):
        return self.resource

    def update_one(self, query, update):
        self.updates.append(update["$set"])


def test_safe_filename_strips_posix_windows_paths_and_null_bytes():
    assert materials.safe_filename("../../lecture.pdf") == "lecture.pdf"
    assert materials.safe_filename(r"C:\\private\\lecture.pdf") == "lecture.pdf"
    assert materials.safe_filename("lecture\x00.pdf") == "lecture.pdf"


def test_office_archive_requires_expected_document_structure():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", "<document>notes</document>")
    assert materials.validate_file(
        "notes.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        payload.getvalue(),
    ) == ".docx"


def test_office_archive_rejects_zip_bomb_style_compression_ratio():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "A" * (1024 * 1024))
    with pytest.raises(ValueError, match="compression ratio"):
        materials.validate_file(
            "notes.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            payload.getvalue(),
        )


def test_image_dimensions_are_bounded_before_processing(monkeypatch):
    monkeypatch.setattr(materials, "MAX_IMAGE_PIXELS", 100)
    payload = io.BytesIO()
    Image.new("RGB", (11, 10)).save(payload, format="PNG")
    with pytest.raises(ValueError, match="dimensions"):
        materials.validate_file("diagram.png", "image/png", payload.getvalue())


def test_semantic_index_failure_keeps_extracted_resource_searchable(monkeypatch):
    resource_id = ObjectId("64b000000000000000000001")
    resource = {
        "_id": resource_id,
        "file": b"lesson content",
        "extension": ".txt",
        "course_id": 4,
        "filename": "lesson.txt",
        "title": "Lesson",
    }
    fake_resources = FakeResources(resource)
    monkeypatch.setattr(materials.mongo_db, "resources", fake_resources)
    monkeypatch.setattr(materials, "extract_content", lambda data, suffix: ("Extracted lesson content", {}))
    monkeypatch.setattr(materials, "index_resource", lambda item: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    monkeypatch.setattr(materials, "clear_search_cache", lambda: None)

    assert materials.prepare_resource(str(resource_id)) is True
    final = fake_resources.updates[-1]
    assert final["processing_status"] == "READY"
    assert final["extraction_status"] == "READY"
    assert final["indexing_status"] == "LEXICAL_ONLY"
    assert final["indexing_error"]
    assert not any(update.get("processing_status") == "FAILED" for update in fake_resources.updates)


def test_extraction_failure_is_still_reported_as_failed(monkeypatch):
    resource_id = ObjectId("64b000000000000000000002")
    resource = {
        "_id": resource_id,
        "file": b"invalid",
        "extension": ".txt",
        "course_id": 4,
        "filename": "lesson.txt",
        "title": "Lesson",
    }
    fake_resources = FakeResources(resource)
    monkeypatch.setattr(materials.mongo_db, "resources", fake_resources)
    monkeypatch.setattr(materials, "extract_content", lambda data, suffix: (_ for _ in ()).throw(ValueError("cannot extract")))
    monkeypatch.setattr(materials, "clear_search_cache", lambda: None)

    assert materials.prepare_resource(str(resource_id)) is False
    assert fake_resources.updates[-1]["processing_status"] == "FAILED"
    assert fake_resources.updates[-1]["extraction_status"] == "FAILED"
