import importlib.util
import re
from pathlib import Path

import pytest

from scripts.make_starter import SOURCE, make_starter

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"# === LIVE CODING START ===\n(.*?)    # === LIVE CODING END ===", re.DOTALL)


def test_starter_replaces_only_the_fence():
    source = SOURCE.read_text(encoding="utf-8")
    starter = make_starter(source)
    stub = FENCE.search(starter)[1]
    assert [f"TODO {n}" in stub for n in range(1, 5)] == [True] * 4
    assert 'raise NotImplementedError("Live-code me!' in stub
    assert FENCE.sub("", starter) == FENCE.sub("", source)


async def test_starter_runs_and_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")  # genai.Client needs a key at import
    path = tmp_path / "agent.py"
    path.write_text(make_starter(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("starter_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(NotImplementedError, match="Live-code me!"):
        await module.run_agent(bridge=type("FakeBridge", (), {"tool_event": None})())


@pytest.mark.parametrize("path", ["app/agent.py", *sorted(p.as_posix() for p in Path(ROOT, "checkpoints").glob("*.py"))])
def test_fence_is_at_most_20_lines(path):
    fence = FENCE.search(Path(ROOT, path).read_text(encoding="utf-8"))[1]
    assert len(fence.splitlines()) <= 20


def test_final_checkpoint_matches_agent():
    final = Path(ROOT, "checkpoints", "step4_bargein.py").read_text(encoding="utf-8")
    assert FENCE.search(final)[1] == FENCE.search(SOURCE.read_text(encoding="utf-8"))[1]
