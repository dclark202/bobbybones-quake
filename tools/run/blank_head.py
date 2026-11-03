"""(1.3b) a copy of a save with the strategy head's own scores taken out of his target choice (head2.add 0: the hands' rows alone), for the
check "the head blanked": play the copy against the opponent the save was checked against; a head that adds something plays worse blanked.
    python tools/run/blank_head.py <save.pt> <out.pt>
then, e.g.:  python tools/run/head2head.py blank13b_<u> duel_gru_1_3b <out.pt> 8 <b1.2d's end> 8 --games 20"""
import sys

import torch


def main():
    src, out = sys.argv[1], sys.argv[2]
    ck = torch.load(src, map_location="cpu", weights_only=False)
    sd = ck["model"]
    assert "head2.add" in sd and float(sd["head2.add"]) > 0, "this save's head has no add (nothing to blank)"
    sd["head2.add"] = torch.zeros_like(sd["head2.add"])
    torch.save(ck, out)
    print("wrote {}: the head's scores out of his target choice (add 0), everything else as {}".format(out, src))


if __name__ == "__main__":
    main()
