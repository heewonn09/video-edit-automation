import json
from unittest.mock import patch
from shortform.cli import main
from shortform.scene_schema import Script, Scene


@patch("shortform.cli.generate_script")
def test_cli_writes_script_json(mock_generate, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    mock_generate.return_value = Script(
        title="테스트 제목",
        scenes=[Scene(1, "나레이션", "연출", 5.0)],
    )

    main(["--topic", "테스트 주제"])

    out_files = list((tmp_path / "output" / "scripts").glob("*.json"))
    assert len(out_files) == 1
    saved = json.loads(out_files[0].read_text(encoding="utf-8"))
    assert saved["title"] == "테스트 제목"

    captured = capsys.readouterr()
    assert "테스트 제목" in captured.out


def test_cli_requires_topic_or_url(capsys):
    try:
        main([])
        assert False, "expected SystemExit"
    except SystemExit:
        pass
