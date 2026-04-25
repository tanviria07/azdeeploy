from pathlib import Path

from azdeeploy.llm.schemas import Diagnosis
from azdeeploy.patches.patch_parser import generate_fixes


def test_generate_fixes_for_missing_requirements(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\ndependencies = ['fastapi', 'uvicorn']\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )

    diagnosis = Diagnosis(
        root_cause="Missing requirements.txt caused App Service build detection to fail.",
        confidence="high",
        evidence=[],
        recommended_fix="Create requirements.txt with the runtime dependencies.",
        azure_commands=[],
        code_or_config_patch=None,
        risk_level="low",
    )

    fixes = generate_fixes(diagnosis, tmp_path)

    assert any(
        fix["file_writes"].get(str(tmp_path / "requirements.txt")) == "fastapi\nuvicorn\n"
        for fix in fixes
    )


def test_generate_fixes_builds_startup_and_env_commands(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.azure").write_text("API_KEY=secret\n", encoding="utf-8")

    diagnosis = Diagnosis(
        root_cause="The startup command is wrong and a missing environment variable causes boot failure.",
        confidence="medium",
        evidence=[],
        recommended_fix="Set the startup command and missing environment variables.",
        azure_commands=[],
        code_or_config_patch=None,
        risk_level="medium",
    )

    fixes = generate_fixes(diagnosis, tmp_path)
    commands = [command for fix in fixes for command in fix["commands_to_run"]]

    assert any("az webapp config set" in command and "--startup-file" in command for command in commands)
    assert any("az webapp config appsettings set" in command and "API_KEY=secret" in command for command in commands)


def test_generate_fixes_applies_unified_diff(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("value = 1\n", encoding="utf-8")

    diagnosis = Diagnosis(
        root_cause="Code needs a small patch.",
        confidence="medium",
        evidence=[],
        recommended_fix="Apply the suggested patch.",
        azure_commands=[],
        code_or_config_patch=(
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            "-value = 1\n"
            "+value = 2\n"
        ),
        risk_level="medium",
    )

    fixes = generate_fixes(diagnosis, tmp_path)

    assert any(
        fix["file_writes"].get(str(app_path)) == "value = 2\n"
        for fix in fixes
    )
