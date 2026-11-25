"""Exercise an installed wheel offline, outside the repository checkout."""

import argparse
import json
import pathlib
import subprocess
import tempfile
import zipfile
from collections.abc import Sequence


def run(
    python: str,
    arguments: Sequence[str],
    directory: pathlib.Path,
    *,
    expected: int = 0,
) -> None:
    """Run a CLI operation with its documented coverage exit status."""
    completed = subprocess.run(
        [python, "-m", "convosignal", *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError(
            f"Installed command failed: {arguments[0]} "
            f"(exit {completed.returncode}, expected {expected})"
        )


def main() -> None:
    """Verify packaged assets, offline replay and both report formats."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    args = parser.parse_args()
    python = str(pathlib.Path(args.python).absolute())
    with tempfile.TemporaryDirectory(prefix="convosignal-installed-") as name:
        directory = pathlib.Path(name)
        metadata = {
            "agent_name": "Installed synthetic agent",
            "stage": "test",
            "report_date": "2026-01-02",
            "stage_basis": "Synthetic fixture",
        }
        (directory / "metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        run(python, ["demo", "--output-dir", "source"], directory)
        run(
            python,
            ["replay", "--run-dir", "source", "--output-dir", "replayed"],
            directory,
            expected=1,
        )
        run(
            python,
            [
                "report",
                "--run-dir",
                "replayed",
                "--metadata",
                "metadata.json",
                "--output-dir",
                "reports",
            ],
            directory,
        )
        report = directory / "reports"
        manifest = json.loads((report / "manifest.json").read_text())
        if (
            manifest["replayed_conversations"] != 6
            or manifest["model_calls"] != 0
        ):
            raise ValueError("Installed replay coverage differs from the demo")
        for name in ("One-Page-Summary.docx", "Explore-Every-Sample.docx"):
            with zipfile.ZipFile(report / name) as archive:
                if archive.testzip() is not None:
                    raise ValueError(
                        "Installed Word output failed ZIP verification"
                    )
        page = (report / "Explore-Every-Sample.html").read_text()
        if "__CSS__" in page or "__SCRIPT__" in page:
            raise ValueError("Installed package is missing report resources")
        print(
            json.dumps(
                {
                    "installed_wheel": "passed",
                    "offline_replayed": 6,
                    "formats": ["html", "docx", "csv", "json"],
                }
            )
        )


if __name__ == "__main__":
    main()
