import json
from unittest.mock import patch
from shortform.cli import main
from shortform.scene_schema import Script, Scene


@patch("shortform.cli.render_script")
@patch("shortform.cli.generate_script")
def test_cli_writes_script_json_and_renders_video(mock_generate, mock_render, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    mock_generate.return_value = Script(
        title="테스트 제목",
        scenes=[Scene(1, "나레이션", "연출", 5.0)],
    )
    mock_render.return_value = tmp_path / "output" / "테스트_제목.mp4"

    main(["--topic", "테스트 주제", "--assets", "my_assets"])

    out_files = list((tmp_path / "output" / "scripts").glob("*.json"))
    assert len(out_files) == 1
    saved = json.loads(out_files[0].read_text(encoding="utf-8"))
    assert saved["title"] == "테스트 제목"

    mock_render.assert_called_once()
    assert mock_render.call_args[0][2] == "my_assets"

    captured = capsys.readouterr()
    assert "테스트 제목" in captured.out


def test_cli_requires_topic_or_url(capsys):
    try:
        main([])
        assert False, "expected SystemExit"
    except SystemExit:
        pass
