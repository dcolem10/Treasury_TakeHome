"""Manifest CSV parsing + filename matching for batch compare mode."""
import pytest

from app.manifest import match_expected, parse_manifest


def test_parses_basic_manifest():
    csv = b"filename,brand_name,alcohol_content\n01.png,Old Tom,45% Alc./Vol.\n"
    m = parse_manifest(csv)
    assert m["01.png"]["brand_name"] == "Old Tom"
    assert m["01.png"]["alcohol_content"] == "45% Alc./Vol."


def test_header_aliases_and_blank_cells():
    csv = b"File,Brand,ABV,Producer\n01.png,Old Tom,,Acme\n"
    m = parse_manifest(csv)
    # 'ABV' blank -> not recorded; aliases normalized.
    assert m["01.png"] == {"brand_name": "Old Tom", "producer": "Acme"}


def test_missing_filename_column_raises():
    with pytest.raises(ValueError):
        parse_manifest(b"brand_name\nOld Tom\n")


def test_match_is_case_and_path_insensitive():
    m = parse_manifest(b"filename,brand_name\nLabel_01.PNG,Old Tom\n")
    assert match_expected(m, "label_01.png")["brand_name"] == "Old Tom"
    assert match_expected(m, "uploads/Label_01.PNG")["brand_name"] == "Old Tom"
    assert match_expected(m, "unknown.png") is None


def test_utf8_bom_is_stripped():
    m = parse_manifest(b"\xef\xbb\xbffilename,brand_name\n01.png,Old Tom\n")
    assert "01.png" in m
