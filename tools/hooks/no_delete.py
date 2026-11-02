"""PreToolUse guard for CLAUDE.md's hard rule 1 (owner, 2026-10-30): a Bash or PowerShell command that would delete files or folders is
not run without the owner's approval (permissionDecision "ask"). Reads the hook's JSON on stdin. It looks at commands in command
position, so a word in a grep pattern or an echo does not count; code that a script file runs is not seen.
    echo '{"tool_input":{"command":"rm x"}}' | python tools/hooks/no_delete.py"""
import json
import re
import sys

START = r"(?:^|[;&|(\n`{]|\bthen\b|\bdo\b|\belse\b|\bxargs\b(?:\s+-\S+)*|\bsudo\b|\bcommand\b|\bexec\b|\bcmd(?:\.exe)?\s+/[ck]\b|\bbash\s+-c\s+[\"']?|\bsh\s+-c\s+[\"']?|-Command\s+[\"']?)\s*(?:@|&\s*)?"
WORDS = r"(?:/\S*/)?(?:rm|rmdir|rd|del|erase|unlink|shred|ri|Remove-Item|Clear-Content|Clear-Item)(?:\.exe)?(?=\s|$|[;&|)\"'])"
PATTERNS = [
    START + WORDS,
    r"\bRemove-Item\b", r"\bClear-Content\b",
    r"\[System\.IO\.(?:File|Directory)\]::Delete\b",
    r"\bgit\s+clean\b",
    r"\bgit\s+worktree\s+remove\b[^\n;&|]*(?:--force|-f\b)",
    r"\bfind\b[^\n;&|]*\s-delete\b",
    r"\bfind\b[^\n;&|]*-exec\s+(?:rm|shred|unlink)\b",
    r"\bos\.(?:remove|unlink|rmdir|removedirs)\s*\(",
    r"\bshutil\.rmtree\s*\(",
    r"\.(?:unlink|rmdir)\s*\(",
]
RX = re.compile("|".join("(?:{})".format(p) for p in PATTERNS), re.IGNORECASE)


def main():
    try:
        cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command") or ""
    except ValueError:
        return 0
    m = RX.search(cmd)
    if m:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "Hard rule 1: this command looks like a delete ({!r}). It needs the owner's approval for this exact delete, and a backup first.".format(m.group(0).strip()[:60]),
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
