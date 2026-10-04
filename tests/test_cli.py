import subprocess
import sys
from pathlib import Path


def test_cli_missing_input_reports_failure_without_output(tmp_path):
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project / 'process_json.py'), *['--input', 'missing.json', '--output', 'unused', '--field', 'id:id']],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert 'ERROR:' in result.stderr
    assert not (tmp_path / 'unused').exists()
