"""Aim style of the subject in play-test aim rooms, from a session's per-frame log (docs/guides/LOGS.md).

    python tools/aim_style.py data/duellive/sessions/<session>

Per room (rockets, rail, lightning gun): shots, the wait between the end of a reload and the next shot, crosshair
error at the moment of the shot, how the fire button is used (held share, presses per minute, mean hold), and how
fast the view moves (median, 95th percentile, maximum, in degrees per second).
"""
import sys,csv,numpy as np,collections
S=sys.argv[1]
rows=list(csv.DictReader(open(S+"/frames.csv")))
REFIRE={"rl":0.8,"rg":1.5,"lg":0.05}
out={}
for w,col in (("rl","o_ammo_rl"),("rg","o_ammo_rg"),("lg","o_ammo_lg")):
    for room in ("walk","jump","env"):
        r=[x for x in rows if x["drill"]=="room:aim/%s/%s"%(w,room)]
        if len(r)<100: continue
        t=np.array([float(x["t"]) for x in r]); am=np.array([float(x[col]) for x in r]); fire=np.array([int(x["o_fire"]) for x in r]); err=np.array([float(x["o_aim_err"]) for x in r]); los=np.array([int(x["los"]) for x in r])
        yaw=np.array([float(x["o_yaw"]) for x in r]); pit=np.array([float(x["o_pitch"]) for x in r])
        shot=np.nonzero(np.diff(am)<0)[0]+1
        dyaw=np.abs((np.diff(yaw)+180)%360-180); turn=np.hypot(dyaw,np.diff(pit))/0.025
        d=dict(shots=len(shot))
        if w!="lg" and len(shot)>1:
            gaps=np.diff(t[shot]); d["mean_gap_after_reload_ms"]=round(float(np.mean(np.clip(gaps-REFIRE[w],0,None))*1000)); d["median_gap_ms"]=round(float(np.median(np.clip(gaps-REFIRE[w],0,None))*1000))
        d["aim_err_at_shot_deg"]=round(float(np.mean(err[shot])),1) if len(shot) else None
        d["fire_held_share"]=round(float(fire.mean()),2)
        tog=np.abs(np.diff(fire)).sum(); d["trigger_presses_per_min"]=round(float(tog/2/(len(r)*0.025/60)),1)
        runs=[]; c=0
        for f in fire:
            if f: c+=1
            elif c: runs.append(c); c=0
        if c: runs.append(c)
        d["mean_hold_s"]=round(float(np.mean(runs))*0.025,2) if runs else 0
        d["view_speed_deg_s_median"]=round(float(np.median(turn))); d["view_speed_p95"]=round(float(np.percentile(turn,95))); d["view_speed_max"]=round(float(turn.max()))
        out["%s/%s"%(w,room)]=d
for k,v in out.items(): print(k,v)
