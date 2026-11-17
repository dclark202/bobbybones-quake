"""2.2a, the review: the guards. The smoke's small trainer (3 updates, --overlap 1 --learn-nosync 1) with a fault injected (O22_FAULT):
  rows   a failure in 2.2a's rows in the rollout from update 2 on: 2.2a's silent parts go off (MAJOR in the trainer's log), the desc lesson is
         recorded as skipped with its reason in rec out22 (and the ramp's MAJOR line), the built 17-output outlook learns on (rows, not off)
  oom    an out-of-memory in desc_notrk's lesson: that part alone off (rec out22 parts_off, MAJOR), desc and desc_nomap learn on
  oom_once  the same fault once (the first lesson of a process): the part stays off and named afterwards, never retried
    QLBOT_ROOT=... python docs/runs/2.2/2.2a/fault_test.py <start file> <2.1d's opt> <anchor a> <anchor b>"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("QLBOT_ROOT") or ""
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TAG = os.environ.get("TEST_TAG", "")


def arm(fault):
    tag = TAG + "_fault_" + fault
    env = dict(os.environ, TEST_TAG=tag, SMOKE_UPDATES="3", O22_FAULT=fault, SMOKE_LEAGUE="0")
    r = subprocess.run([sys.executable, os.path.join(HERE, "smoke.py")] + sys.argv[1:5], env=env, capture_output=True, text=True, creationflags=NOWIN)
    D = os.path.join(DATA, "data", "sim_runs", "scratch_22a_smoke" + tag)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"))] if os.path.exists(os.path.join(D, "metrics.jsonl")) else []
    log = open(os.path.join(DATA, "data", "sim_runs", "scratch_22a_smoke" + tag + ".log"), encoding="utf-8", errors="replace").read()
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_22a.py"), "x", "--dir", D, "--once"], capture_output=True, text=True, creationflags=NOWIN)
    wl = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(D, "watch", "watch.log")) else ""
    return M, log, wl


def main():
    ok = True

    def chk(nm, good, more=""):
        nonlocal ok
        ok = ok and bool(good)
        print(("PASS  " if good else "FAIL  ") + nm + (" | " + str(more)[:900] if more != "" else ""), flush=True)
    M, log, wl = arm("rows")
    o_ = [m_.get("outlook") or {} for m_ in M]
    q_ = [m_.get("out22") or {} for m_ in M]
    chk("rows: 3 updates and the resume's one; the built outlook learns every update (rows, a loss, not off)", len(M) == 4 and all((x_.get("rows") or 0) > 0 and x_.get("loss") is not None
        and not x_.get("off") for x_ in o_), [(x_.get("rows"), x_.get("loss"), x_.get("off")) for x_ in o_])
    chk("rows: once the fault comes (rollout 2: with the overlap, before update 1's lesson), 2.2a's parts off and the desc lesson recorded as "
        "skipped with its reason and the run's count, every update to the end of the process; MAJOR in the trainer's log",
        all(x_.get("off") and x_.get("desc_skipped") and x_.get("desc_skipped_n") for x_ in q_[:3]) and q_[2].get("desc_skipped_n") == 3
        and "MAJOR PROBLEM: 2.2a's silent lessons" in log, [(x_.get("off"), x_.get("desc_skipped"), x_.get("desc_skipped_n")) for x_ in q_])
    chk("rows: the ramp's MAJOR lines (the desc lesson did not run; 2.2a's parts failed)", "THE DESC OUTLOOK'S LESSON DID NOT RUN" in wl
        and "2.2a'S SILENT LESSONS OR READOUTS FAILED" in wl)
    M, log, wl = arm("oom")
    q_ = [m_.get("out22") or {} for m_ in M]
    chk("oom: desc_notrk's part off by an out-of-memory (MAJOR, named), desc and desc_nomap learn every update, 2.2a not off",
        len(M) == 4 and all("the desc outlook desc_notrk" in (x_.get("parts_off") or []) and not x_.get("off")
                            and (x_.get("desc") or {}).get("desc", {}).get("kind") and (x_.get("desc") or {}).get("desc_nomap", {}).get("kind") for x_ in q_)
        and "OUT OF MEMORY in 2.2a's the desc outlook desc_notrk" in log, [(x_.get("parts_off"), x_.get("off")) for x_ in q_])
    chk("oom: the ramp's MAJOR line names the part", "turned OFF by an out-of-memory" in wl)
    M, log, wl = arm("oom_once")                             # (the second review: a fault once; the part must STAY off, not retry)
    q_ = [m_.get("out22") or {} for m_ in M]
    sib_ = [((x_.get("desc") or {}).get("desc_notrk") or {}) for x_ in q_[:3]]
    chk("oom_once: one out-of-memory in desc_notrk's first lesson: off and named in every later update of the process, never retried (its record "
        "says off earlier), desc learns on", len(M) == 4 and all("the desc outlook desc_notrk" in (x_.get("parts_off") or []) for x_ in q_[:3])
        and all(s_.get("off") == "out of memory earlier" for s_ in sib_[1:3]) and log.count("OUT OF MEMORY in 2.2a's the desc outlook desc_notrk") == 2
        and all((x_.get("desc") or {}).get("desc", {}).get("kind") for x_ in q_), ([x_.get("parts_off") for x_ in q_], [s_.get("off") for s_ in sib_]))
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
