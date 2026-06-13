import json
import zipfile

from apexdev.cli import main
from apexdev.repo_overlay import apply_source


def test_repo_apply_preview_and_apply_path(tmp_path):
    repo = tmp_path / "repo"
    incoming = tmp_path / "incoming"
    repo.joinpath("src/pkg").mkdir(parents=True)
    incoming.joinpath("src/pkg").mkdir(parents=True)
    target = repo / "src/pkg/module.py"
    target.write_text("old", encoding="utf-8")
    incoming.joinpath("src/pkg/module.py").write_text("new", encoding="utf-8")

    preview = apply_source(incoming, repo=repo)
    assert preview["summary"]["matched_count"] == 1
    assert target.read_text(encoding="utf-8") == "old"

    applied = apply_source(incoming, repo=repo, apply=True)
    assert applied["summary"]["overwritten_count"] == 1
    assert target.read_text(encoding="utf-8") == "new"
    assert applied["matches"][0]["backup_path"]


def test_repo_apply_zip_unique_name_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.joinpath("nested").mkdir(parents=True)
    target = repo / "nested/config.toml"
    target.write_text("old", encoding="utf-8")
    archive = tmp_path / "incoming.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("config.toml", "new")

    report = apply_source(archive, repo=repo, match_mode="auto")
    assert report["matches"][0]["method"] in {"suffix", "name"}

    main(["repo", "apply", str(archive), "--repo", str(repo), "--apply", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["overwritten_count"] == 1
    assert target.read_text(encoding="utf-8") == "new"


def test_repo_apply_single_file_explicit_target_and_create_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = tmp_path / "loose.py"
    source.write_text("print('new')\n", encoding="utf-8")
    target = repo / "src/apexdev/loose.py"

    preview = apply_source(source, repo=repo, target="src/apexdev/loose.py", create_missing=True)
    assert preview["summary"]["would_create_count"] == 1
    assert preview["matches"][0]["target_path"] == "src/apexdev/loose.py"

    applied = apply_source(source, repo=repo, target="src/apexdev/loose.py", create_missing=True, apply=True)
    assert applied["summary"]["created_count"] == 1
    assert target.read_text(encoding="utf-8") == "print('new')\n"


def test_repo_apply_similarity_is_explicit(tmp_path):
    repo = tmp_path / "repo"
    repo.joinpath("src/apexdev").mkdir(parents=True)
    target = repo / "src/apexdev/openrouter.py"
    target.write_text("old", encoding="utf-8")
    source = tmp_path / "open-router.py"
    source.write_text("new", encoding="utf-8")

    auto = apply_source(source, repo=repo)
    assert auto["summary"]["no_match_count"] == 1

    fuzzy = apply_source(source, repo=repo, match_mode="similarity")
    assert fuzzy["summary"]["matched_count"] == 1
    assert fuzzy["matches"][0]["method"] == "similarity"
