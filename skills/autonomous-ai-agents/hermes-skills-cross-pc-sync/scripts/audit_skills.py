"""Compare skill-archive copies against the live Hermes skills dir by content hash.

Usage: python audit_skills.py <copy_dir> [<copy_dir> ...]
Each copy_dir contains skills/<name>/... (flat or categorised).
Per skill prints status vs the live dir for each copy
('=' identical, 'diff' differs, '-' absent) and, for diffs, mtime + line counts.
"""
import hashlib, os, sys, time

LIVE = os.path.expandvars(r"%LOCALAPPDATA%\hermes\skills")


def scan(base):
    out = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, base).replace("\\", "/")] = hashlib.md5(open(p, "rb").read()).hexdigest()[:8]
    return out


def skill_dirs(base):
    idx = {}
    for dp, _, fs in os.walk(base):
        if "SKILL.md" in fs and "/.archive" not in dp.replace("\\", "/"):
            idx[os.path.basename(dp)] = dp
    return idx


def stamp(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    return f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(p)))} {len(s.splitlines())}L"


def main(copies):
    live = skill_dirs(LIVE)
    per_copy = {c: skill_dirs(c) for c in copies}
    names = sorted(set().union(*[set(v) for v in per_copy.values()]))
    print("columns:", copies)
    for n in names:
        lp = live.get(n)
        L = scan(lp) if lp else None
        res = []
        for c in copies:
            d = per_copy[c].get(n)
            res.append("-" if not d else ("=" if L == scan(d) else "diff"))
        where = os.path.relpath(lp, LIVE) if lp else "NOT INSTALLED"
        print(f"{n:34} {where:48} {res}")
        if "diff" in res and lp:
            print("    LIVE", stamp(os.path.join(lp, "SKILL.md")))
            for c in copies:
                d = per_copy[c].get(n)
                if d:
                    print("   ", os.path.basename(c), stamp(os.path.join(d, "SKILL.md")))


if __name__ == "__main__":
    main(sys.argv[1:])
