"""(brainppl) the fit's report (sim/brain_fit.py report_<tag>.json) in a few lines: held-out sets, before -> after"""
import json
import sys

r = json.load(open(sys.argv[1]))
print("data:", {k: v["hours"] for k, v in r["data"].items()}, "best epoch", r.get("best_epoch"))
for k in r["before"]:
    b, a = r["before"][k], r.get("after", {}).get(k, {})
    f = lambda d, *p: (lambda x: x)(_g(d, p))
    print("==", k, "ticks", b["ticks"])
    pe = b["place_err_median"]
    print("  place err median  all {} -> {} | 0-1s {} -> {} | 1-3s {} -> {} | 3-6s {} -> {} | 6-15s {} -> {} | 15s+ {} -> {}".format(
        pe["all"], a.get("place_err_median", {}).get("all"), *[x for kk in ("0-1s", "1-3s", "3-6s", "6-15s", "15-s")
                                                               for x in (pe.get(kk), a.get("place_err_median", {}).get(kk))]))
    print("  zone top3 {} -> {}   top1 {} -> {}".format(b["zone_top3"], a.get("zone_top3"), b["zone_top1"], a.get("zone_top1")))
    for h in ("1s", "2s", "4s"):
        print("  ahead {}: median {} -> {}  (stays where believed: {} -> {})".format(h, b["ahead"][h]["median"], a.get("ahead", {}).get(h, {}).get("median"),
                                                                                      b["ahead"][h]["stays_median"], a.get("ahead", {}).get(h, {}).get("stays_median")))
    print("  target top1 {} -> {} (items {} -> {}; most common class {}, n {})".format(b.get("target_top1"), a.get("target_top1"), b.get("target_top1_items"),
                                                                                    a.get("target_top1_items"), b.get("target_base_most_common"), b.get("target_n")))
    if "appear" in b:
        print("  appear nll {} -> {}  acc {} -> {}  ece {} -> {}".format(b["appear"]["nll"], a.get("appear", {}).get("nll"), b["appear"]["acc"],
                                                                         a.get("appear", {}).get("acc"), b["appear"]["ece"], a.get("appear", {}).get("ece")))
    print("  nll", {kk: (b["nll"][kk], a.get("nll", {}).get(kk)) for kk in b["nll"]})


def _g(d, p):
    for x in p:
        d = d.get(x, {}) if isinstance(d, dict) else None
    return d


if "play" in r:
    for k, v in r["play"].items():
        print("play", k, "frames", v["frames"], "KL/frame", v["kl_per_frame"], "argmax changed mean", v["argmax_changed_any_mean"], "by output", v["argmax_changed"])
if "play_error" in r:
    print("play errors", r["play_error"])
