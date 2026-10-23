"""The skills: valid frontmatter, every command they tell an agent to run exists, and the
safety rules are actually written in the ones that touch money."""
import json
import re
import shlex
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from aptrade.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted((ROOT / "skills").glob("aptrade-*/SKILL.md"))


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^[a-z-]+:", line):
            key, _, val = line.partition(":")
            out[key] = val.strip()
        elif key:
            out[key] = (out[key] + " " + line.strip()).strip()
    out["description"] = out.get("description", "").replace(">-", "").strip()
    return out


def commands(text: str) -> list:
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    cmds = []
    for b in blocks:
        for line in b.splitlines():
            line = line.split("#")[0].strip()
            if line.startswith("aptrade "):
                cmds.append(line)
    return cmds


class TestSkills(unittest.TestCase):
    def test_eleven_valid_skills(self):
        self.assertEqual(len(SKILLS), 11)
        for f in SKILLS:
            fm = frontmatter(f.read_text())
            self.assertEqual(fm["name"], f.parent.name, f)
            self.assertTrue(20 < len(fm["description"]) <= 1024, f)
            self.assertIn("Use when", fm["description"], f)

    def test_every_command_exists(self):
        parser = build_parser()
        for f in SKILLS:
            for cmd in commands(f.read_text()):
                argv = shlex.split(cmd.replace("<plan_id>", "abc123"))[1:]
                with redirect_stderr(StringIO()):
                    try:
                        parser.parse_args(argv)
                    except SystemExit as exc:
                        self.fail(f"{f.parent.name}: `{cmd}` does not parse ({exc})")

    def test_money_skills_carry_the_rules(self):
        broker = (ROOT / "skills/aptrade-broker/SKILL.md").read_text()
        self.assertIn("aptrade live execute <plan_id> --live", broker)
        self.assertIn("Do not try to run it yourself", broker)
        for name in ("aptrade-broker", "aptrade-risk", "aptrade-rebalance", "aptrade-allocate"):
            text = (ROOT / "skills" / name / "SKILL.md").read_text()
            self.assertIn("Never ask the user to paste a key", text, name)
            self.assertIn("never uses leverage", text, name)
        self.assertIn("never call the broker API directly", " ".join((ROOT / "skills/aptrade-risk/SKILL.md").read_text().split()))

    def test_distribution_files(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(plugin["name"], "aptrade")
        self.assertEqual(market["plugins"][0]["source"], "./")
        for link in (".agents/skills", ".claude/skills"):
            p = ROOT / link
            self.assertTrue(p.is_symlink(), link)
            self.assertEqual(sorted(x.name for x in p.iterdir() if x.name.startswith("aptrade-")),
                             [f.parent.name for f in SKILLS])
        self.assertIn("NOT execute", (ROOT / "AGENTS.md").read_text())


if __name__ == "__main__":
    unittest.main()
