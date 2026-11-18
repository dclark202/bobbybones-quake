"""(2.2b's restart, 2026-11-17, the owner's decisions) the item picker (the strategy head, head2) held still.

2.2b's first start switched the item picker's choice lesson off for its first 10 updates while the rest of it kept training under its
forecast's loss: nothing held its outputs, its weapon scores grew (3.1 -> 5.5) and he came to hold the gauntlet a third of the time
(the update-10 check 0-200). The restart:

  --h2-freeze 1      through the run's first `window` updates (--h2-choice-warm, counted from the run's start by metrics.jsonl's lines:
                     a resume does not start the window again) every parameter of head2 is frozen except its forecast's last layer
                     (FORECAST: `v.`, and `ins_vv.` where the head has it): no gradient (set to None before the clip and the step, so Adam
                     neither steps it nor moves its moments), no decoupled decay (the trainer's decays are gated on `frozen()`), no lesson
                     of the parts with their own Adam inside it (the slow plan `plan.`, the tracker `trk.`: the trainer skips their steps).
  --h2-wsc-freeze 1  the same for the weapon scores (`wsc.`, `winp.`) for the whole run.

The proof, every update (`record()`, into metrics.jsonl as "h2_freeze"): the largest absolute difference of every held parameter against
its value at this process's start, by name (exactly 0 is the pass), the forecast's last layer's movement, and the item picker's outputs
on a fixed batch of inputs (its goal scores `target`, its weapon scores `wsc`, the plan it hands down `plan_out`) against the start's,
bit for bit. A held parameter found moved is put back (`restored`) and the ramp writes a MAJOR line.
"""
import torch

FORECAST = ("v.", "ins_vv.")
WEAPON = ("wsc.", "winp.")
OWN_ADAM = ("plan.", "trk.")


class Freeze:
    def __init__(self, mod, window, done0, freeze, wfreeze, seed=4057, n_probe=64):
        self.mod, self.window, self.done0 = mod, int(window), int(done0)
        self.freeze, self.wfreeze = bool(freeze), bool(wfreeze)
        self.names = [n_ for n_, _ in mod.named_parameters()]
        with torch.no_grad():
            self.ref = {n_: p_.detach().clone() for n_, p_ in mod.named_parameters()}
            g_ = torch.Generator().manual_seed(int(seed))
            W_ = int(mod.inp.in_features) + (int(mod.winp.in_features) if hasattr(mod, "winp") else 0)
            S_ = int(mod.gru.hidden_size)
            dev_ = next(mod.parameters()).device
            self.u = (torch.randn(n_probe, W_, generator=g_) * 0.5).half().float().to(dev_)
            self.s0 = (torch.randn(n_probe, S_, generator=g_) * 0.3).to(dev_)
            self.out0 = self.outputs()
        self.on = False
        self.run_upd = 0

    # -- which parameters are held ------------------------------------------------------------------------------------------------
    def set_update(self, update):
        """at the top of an update (this process's `update`): the run's update number and whether the window holds"""
        self.run_upd = self.done0 + int(update)
        self.on = bool(self.freeze and self.run_upd <= self.window)
        return self.on

    def frozen(self, name):
        """name (head2's parameter, without the prefix): held in this update"""
        if self.wfreeze and name.startswith(WEAPON):
            return True
        return bool(self.on and not name.startswith(FORECAST))

    def own_adam_frozen(self, prefix):
        """the slow plan ('plan.') or the tracker ('trk.'): their own lesson skipped in this update"""
        assert prefix in OWN_ADAM, prefix
        return bool(self.on)

    def drop_grads(self):
        """before the clip and the step: every held parameter's gradient set to None (Adam skips it: no step, no moment)"""
        for n_, p_ in self.mod.named_parameters():
            if self.frozen(n_):
                p_.grad = None

    # -- the proof --------------------------------------------------------------------------------------------------------------
    def outputs(self):
        import head2 as head2_
        m_ = self.mod
        with torch.no_grad():
            s_ = m_.gru(head2_.pre(m_, self.u), self.s0)
            o_ = dict(target=m_.target(s_), plan_out=m_.plan_out(s_))
            if hasattr(m_, "wsc"):
                o_["wsc"] = m_.wsc(s_)
        return {k_: v_.detach().clone() for k_, v_ in o_.items()}

    def record(self, restore=True):
        """after the update's learning: the proof (see the module's note); a held parameter that moved is put back"""
        held_, free_, moved_ = {}, {}, []
        with torch.no_grad():
            for n_, p_ in self.mod.named_parameters():
                d_ = float((p_.detach() - self.ref[n_]).abs().max()) if p_.numel() else 0.0
                if self.frozen(n_):
                    held_[n_] = d_
                    if d_ != 0.0:
                        moved_.append(n_)
                else:
                    free_[n_] = d_
            if moved_ and restore:
                for n_, p_ in self.mod.named_parameters():
                    if n_ in moved_:
                        p_.copy_(self.ref[n_])
            o_ = self.outputs()
        outs_ = {k_: float((o_[k_] - self.out0[k_]).abs().max()) for k_ in o_}
        fc_ = {n_: d_ for n_, d_ in free_.items() if n_.startswith(FORECAST)}
        return dict(run_update=self.run_upd, window=self.window, on=self.on, weapon_frozen=self.wfreeze,
                    held_max=max(held_.values()) if held_ else 0.0, held_n=len(held_), held_by_name=held_,
                    weapon_max=max([d_ for n_, d_ in held_.items() if n_.startswith(WEAPON)] or [0.0]),
                    forecast_moved=fc_, free_max=max(free_.values()) if free_ else 0.0,
                    outputs_vs_start=outs_, moved=moved_, restored=bool(moved_ and restore))

    def describe(self):
        return ("the item picker held (2.2b restart): {}; {}; the proof (h2_freeze) every update".format(
            "frozen except its forecast's last layer ({}) through the run's update {} (this process starts after {} done)".format(
                [n_ for n_ in self.names if n_.startswith(FORECAST)], self.window, self.done0) if self.freeze else "no window freeze",
            "its weapon scores {} frozen for the whole run".format([n_ for n_ in self.names if n_.startswith(WEAPON)]) if self.wfreeze else
            "its weapon scores learn"))
