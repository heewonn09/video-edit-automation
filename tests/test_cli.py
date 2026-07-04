import json
from pathlib import Path
from unittest.mock import patch
from shortform.cli import main, _slugify
from shortform.scene_schema import Script, Scene


@patch("shortform.cli.render_script")
@patch("shortform.cli.generate_script")
def test_cli_writes_script_json_and_renders_video(mock_generate, mock_render, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    script = Script(
        title="테스트 제목",
        scenes=[Scene(1, "나레이션", "연출", 5.0)],
    )
    mock_generate.return_value = script
    expected_slug = _slugify("테스트 제목")
    expected_video_path = tmp_path / "output" / f"{expected_slug}.mp4"
    mock_render.return_value = expected_video_path

    main(["--topic", "테스트 주제", "--assets", "my_assets"])

    out_files = list((tmp_path / "output" / "scripts").glob("*.json"))
    assert len(out_files) == 1
    saved = json.loads(out_files[0].read_text(encoding="utf-8"))
    assert saved["title"] == "테스트 제목"

    mock_render.assert_called_once()
    # Assert all three arguments to render_script
    assert mock_render.call_args[0][0] is script  # Script object
    assert mock_render.call_args[0][1] == Path("output") / f"{expected_slug}.mp4"  # output path
    assert mock_render.call_args[0][2] == "my_assets"  # assets path

    captured = capsys.readouterr()
    assert "테스트 제목" in captured.out
    # Assert that the video path from render_script return value appears in output
    assert str(expected_video_path) in captured.out


def test_cli_requires_topic_or_url(capsys):
    try:
        main([])
        assert False, "expected SystemExit"
    except SystemExit:
        pass


@patch("shortform.cli._process_one")
def test_cli_batch_processes_each_line_and_continues_on_failure(mock_process, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    batch_file = tmp_path / "topics.txt"
    batch_file.write_text("주제1\n주제2\n", encoding="utf-8")
    mock_process.side_effect = [RuntimeError("실패"), None]

    main(["--batch", str(batch_file)])

    assert mock_process.call_count == 2
    assert mock_process.call_args_list[0][0][0] == "주제1"
    assert mock_process.call_args_list[1][0][0] == "주제2"
