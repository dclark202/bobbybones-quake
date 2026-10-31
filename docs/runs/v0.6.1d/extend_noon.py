"""v0.6.1d to noon, then v0.6.1c against it (owner, 2026-10-31: "Let's extend this run v0.6.1d to noon to watch the performance. And then
run the comparison c/d afterwards"). A run's length is fixed in its process, so: waits for the trainer to end (log ends in "exit"), keeps
that save (keep/policy_915min_v061d.pt + opt), resumes the same folder with the same command for the minutes left to noon and no second
opening of the rescale (--adv-pay-warm 0; only those two differ, settings check), keeps the end at noon (policy_end_v061d.pt + opt), then
plays 160 games, d's end against c's end, as the watcher's checks. Its watcher, self-play logger and live.json carry on. A failed step
stops here, logged in extend_noon.log; nothing deleted.
    python docs/runs/v0.6.1d/extend_noon.py"""
import datetime, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SR = os.path.join(ROOT, "data", "sim_runs")
RUN = "duel_gru_v0_6_1d"
D = os.path.join(SR, RUN)
LOG = D + ".log"
PY = sys.executable
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
os.environ["PANEL_RUN"] = RUN
import panel as P
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]
C_END = os.path.join(SR, "duel_gru_v0_6_1c", "keep", "policy_end_v061c.pt")


def say(s):
    with open(os.path.join(HERE, "extend_noon.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")


def last_line():
    with open(LOG, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 400))
        L = f.read().decode("utf-8", "replace").strip().splitlines()
    return L[-1] if L else ""


def wait_exit():
    while not last_line().startswith("exit"):
        time.sleep(30)
    time.sleep(60)
    say("the trainer ended: " + last_line())


def keep(pol, opt):
    for a, b in (("policy.pt", pol), ("opt.pt", opt)):
        dst = os.path.join(D, "keep", b)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(D, a), dst)
    say("kept " + pol + " + " + opt)


def compare(pol):
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    sets = P.settings(0.0, pol)
    res, won, lost = {}, 0, 0
    for w in range(0, len(MAPS), 5):
        jobs = []
        for mp in MAPS[w:w + 5]:
            js = os.path.join(HERE, "cmp_d_c_{}.json".format(mp))
            cmd = [PY, "tools/duel_eval.py", "--run", RUN, "--policy", pol, "--opp", "policy:" + C_END, "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"),
                   "--map", mp, "--games", "16", "--minutes", "10", "--procs", "2", "--swap", "--json", js, "--react-ms", "125", "--acquire-ms", "225",
                   "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600"]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            jobs.append((mp, js, subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(js + ".log", "w"), stderr=subprocess.STDOUT)))
        for mp, js, p in jobs:
            p.wait()
            try:
                v = json.load(open(js))["maps"][mp]
                res[mp] = "{}-{} {:.0%}".format(v["won"], v["lost"], v["frag_share"])
                won, lost = won + v["won"], lost + v["lost"]
            except Exception as e:                                   # noqa: BLE001
                res[mp] = "error " + str(e)
    say("d's end against c's end: {}-{} win rate {:.1%} | {}".format(won, lost, won / max(1, won + lost), res))


def main():
    say("waiting for the 915-minute end")
    wait_exit()
    keep("policy_915min_v061d.pt", "opt_915min_v061d.pt")
    noon = datetime.datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    mins = int((noon - datetime.datetime.now()).total_seconds() // 60)
    if mins < 5:
        say("past noon ({} min): not resumed".format(mins))
    else:
        t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read()
        for a, b in (("--minutes 915 --gamma", "--minutes {} --gamma".format(mins)), ("--adv-pay-warm 30 ", "--adv-pay-warm 0 ")):
            assert t.count(a) == 1, a
            t = t.replace(a, b)
        t = t.replace("set ROOT=%~dp0..\\..\\..", "set ROOT=" + ROOT).replace("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd"))
        cmd = os.path.join(D, "watch", "train_to_noon.cmd")
        open(cmd, "w", encoding="ascii", newline="").write(t)
        r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "check_settings.py"), cmd, "--ref", os.path.join(HERE, "train.cmd"), "--allow=--minutes,--adv-pay-warm"], cwd=ROOT, capture_output=True, text=True)
        say(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "settings check: no output")
        if r.returncode:
            say("SETTINGS CHECK FAILED: not resumed; the comparison runs on the 915-minute end")
        else:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write("resumed\n")                                 # (the log no longer ends in exit)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
            subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env, creationflags=0x08000000)
            say("resumed for {} min".format(mins))
            time.sleep(120)
            wait_exit()
    keep("policy_end_v061d.pt", "opt_end_v061d.pt")
    compare(os.path.join(D, "keep", "policy_end_v061d.pt"))


if __name__ == "__main__":
    main()
