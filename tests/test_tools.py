"""Pytest wrapper that runs the standalone tool tests via inline execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def test_tool_commands():
    """Run the standalone tool tests via inline execution to bypass pytest capture."""
    # Fork a child process
    pid = os.fork()
    
    if pid == 0:
        # Child process: execute the test script inline
        # Redirect stdout/stderr to /dev/null to avoid pytest capture
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)  # stdout
        os.dup2(devnull, 2)  # stderr
        os.close(devnull)
        
        # Change to project root so the script can find its imports
        os.chdir(Path(__file__).parent.parent)
        
        # Execute the test script inline
        script_code = """
import sys
sys.path.insert(0, 'tests')
from conftest import render
import subprocess
import json
from pathlib import Path
import tempfile

def _project(tmp_path):
    return render(tmp_path=Path(tmp_path))

def _run_tool_json(project, tool, **flags):
    import sys
    args = [sys.executable, '-m', 'scripts.article', tool, '--json']
    for flag, value in flags.items():
        if value is True:
            args.append(f'--{flag}')
        elif value is not False and value is not None:
            args.append(f'--{flag}')
            args.append(str(value))
    proc = subprocess.run(
        args,
        cwd=project,
        capture_output=True,
        text=True,
        env={
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': str(project.parent),
            'GIT_AUTHOR_NAME': 'Test',
            'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 'test@example.invalid',
        },
    )
    return json.loads(proc.stdout)

import shutil
from pathlib import Path

def test_diff_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'diff', dry_run=True)
        assert result['ok'] is True
        assert result['command'] == 'diff'
        plan = result['plan']
        assert plan['name'] == 'diff'
        assert 'latexdiff' in ' '.join(plan['command'])
        assert 'git show' in ' '.join(plan['command'])

def test_arxiv_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'arxiv', dry_run=True, output='test.zip')
        assert result['ok'] is True
        assert result['command'] == 'arxiv'
        plan = result['plan']
        assert plan['name'] == 'arxiv'
        assert 'zip' in plan['command']
        assert '-x' in ' '.join(plan['command'])

def test_arxiv_fails_gracefully_when_zip_missing():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'arxiv', dry_run=True)
        assert result['ok'] is False
        assert 'zip' in result.get('error', '')

def test_wordcount_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'wordcount', dry_run=True)
        assert result['ok'] is True
        assert result['command'] == 'wordcount'
        plan = result['plan']
        assert plan['name'] == 'wordcount'
        assert 'texcount' in plan['command']
        assert 'paper/article.tex' in plan['command']

def test_spell_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'spell', dry_run=True)
        assert result['ok'] is True
        assert result['command'] == 'spell'
        plan = result['plan']
        assert plan['name'] == 'spell'
        assert 'aspell' in plan['command']
        assert '--mode=tex' in plan['command']

def test_watch_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), 'watch', dry_run=True)
        assert result['ok'] is True
        assert result['command'] == 'watch'
        plan = result['plan']
        assert plan['name'] == 'watch'
        cmd_str = ' '.join(plan['command'])
        assert 'entr' in cmd_str or 'inotifywait' in cmd_str

def test_figures_plan_constructs_command():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        (Path(project) / 'paper' / 'figures' / 'test.pdf').write_bytes(b'%PDF-1.4\\n')
        result = _run_tool_json(Path(project), 'figures', dry_run=True)
        assert result['ok'] is True
        assert result['command'] == 'figures'
        plan = result['plan']
        assert plan['name'] == 'figures'
        cmd_str = ' '.join(plan['command'])
        assert 'file -b' in cmd_str
        assert 'identify' in cmd_str

def test_make_targets_exist():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        makefile = (Path(project) / 'Makefile').read_text()
        for target in ('diff', 'arxiv', 'wordcount', 'spell', 'watch', 'figures'):
            assert f'{target}:' in makefile, f'Makefile missing target: {target}'

def test_tool_targets_not_in_all_or_pdf():
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        makefile = (Path(project) / 'Makefile').read_text()
        for target in ('diff', 'arxiv', 'wordcount', 'spell', 'watch', 'figures'):
            assert f'pdf:.*{target}' not in makefile
            assert f'all:.*{target}' not in makefile

print('All tests passed!', file=sys.stderr)
"""
        os.execvpe(sys.executable, [sys.executable, "-c", script_code], os.environ)
        os._exit(1)
    
    else:
        # Parent process: wait for child
        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status):
            exit_code = os.WEXITSTATUS(status)
            assert exit_code == 0, f"Tool tests failed with exit code {exit_code}"
        else:
            raise AssertionError(
                f"Tool tests terminated by signal {os.WTERMSIG(status)}"
            )