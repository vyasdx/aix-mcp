"""Keep the skills honest: valid front matter, real tool names, working links."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
SKILL_DIRS = sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())
SERVER = (ROOT / "src" / "aix_mcp" / "server.py").read_text(encoding="utf-8")
TOOLS = set(re.findall(r"def (aix_\w+)\(", SERVER))
FINDINGS = set(re.findall(
    r'"((?:perf_)?[a-z_]+)"',
    (ROOT / "src" / "aix_mcp" / "findings.py").read_text(encoding="utf-8")
    + (ROOT / "src" / "aix_mcp" / "perf.py").read_text(encoding="utf-8"),
))


def _front_matter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md must start with YAML front matter"
    out = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def test_there_are_skills():
    assert len(SKILL_DIRS) >= 6
    assert len(TOOLS) == 9


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda d: d.name)
def test_front_matter(d):
    fm = _front_matter((d / "SKILL.md").read_text(encoding="utf-8"))
    assert fm.get("name") == d.name, "name must match the folder name"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 50 <= len(fm.get("description", "")) <= 1024


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda d: d.name)
def test_tool_and_finding_names_exist(d):
    for f in d.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        for tool in set(re.findall(r"\baix_[a-z_]+(?=\()", text)):
            assert tool in TOOLS, f"{f.name}: unknown tool {tool}"
        for fid in set(re.findall(r"`((?:perf|path|too|hcheck|concurrent|disk|fc|dyntrk|vfchost|npiv|filesystem|check)_?[a-z_]*)`", text)):
            if fid in ("fc_err_recov", "dyntrk") or "_" not in fid:
                continue
            if fid.startswith(("perf_", "path_not", "too_few", "hcheck_disabled", "concurrent_vg",
                               "disk_not", "fc_link", "vfchost_not", "npiv_port", "filesystem_used",
                               "check_missing")):
                assert fid in FINDINGS, f"{f.name}: unknown finding id {fid}"


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda d: d.name)
def test_relative_links_resolve(d):
    for f in d.rglob("*.md"):
        for target in re.findall(r"\]\(((?!https?:)[^)#]+)\)", f.read_text(encoding="utf-8")):
            assert (f.parent / target).exists(), f"{f}: broken link {target}"


def test_skills_reference_only_existing_skills():
    names = {d.name for d in SKILL_DIRS}
    for d in SKILL_DIRS:
        for f in d.rglob("*.md"):
            for ref in re.findall(r"\*\*(aix-[a-z-]+)\*\*", f.read_text(encoding="utf-8")):
                assert ref in names, f"{f}: refers to unknown skill {ref}"
