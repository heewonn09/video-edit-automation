from shortform.asset_library import list_assets, AssetInfo


def test_list_assets_classifies_image_and_video(tmp_path):
    (tmp_path / "b_clip.mp4").write_bytes(b"fake")
    (tmp_path / "a_photo.png").write_bytes(b"fake")
    (tmp_path / "ignore.txt").write_bytes(b"fake")

    assets = list_assets(tmp_path)

    assert [a.filename for a in assets] == ["a_photo.png", "b_clip.mp4"]
    assert assets[0].kind == "image"
    assert assets[1].kind == "video"


def test_list_assets_empty_when_folder_missing(tmp_path):
    assert list_assets(tmp_path / "does_not_exist") == []
