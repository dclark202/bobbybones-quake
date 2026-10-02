import os
import sys

from subprocess import check_output

def print_usage():
    print("Usage: {} [-d]".format(sys.argv[0]))

if __name__ == "__main__":
    try:
        version = check_output(["git", "describe", "--long", "--tags", "--dirty", "--always"]).decode().strip()
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
    except Exception:  # vendored copy without minqlx's own git history
        version, branch = "fbdd915", "bobbybones"

    if os.environ.get("MINQLX_VERSION"):
        print(os.environ.get("MINQLX_VERSION"))
    elif len(sys.argv) < 2:
        print("{}-{}".format(version, branch))
    elif sys.argv[1] == "-d":
        print("{}_debug-{}".format(version, branch))
    else:
        print_usage()
