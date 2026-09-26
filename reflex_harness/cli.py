"""python -m reflex_harness run --task X --arm memory [--phase dev] [--pretty] [--save-dir DIR]"""
import argparse
import json
import os
from pathlib import Path

from .controller import ARMS, BUDGET, run_task
from .pretty import Pretty


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reflex_harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--task", required=True)
    r.add_argument("--arm", choices=ARMS, default="memory")
    r.add_argument("--phase", choices=("dev", "eval", "demo"), default="dev",
                   help="demo: rows are tagged phase=demo (run ids demo-...) and stay out of dev/eval data")
    r.add_argument("--repeat", type=int, default=0, help="repeat index (seeds the random arm)")
    r.add_argument("--pretty", action="store_true",
                   help="demo output: one coloured line per event, no raw logs (presentation only)")
    r.add_argument("--save-dir", help="also write the run record (JSON) and the output transcript here")
    args = ap.parse_args(argv)
    if args.pretty:
        pretty = Pretty(model=os.environ.get("CODING_MODEL", "?"))
        doc = run_task(args.task, args.arm, phase=args.phase, repeat=args.repeat,
                       log=lambda m: None, events=pretty)
        transcript = pretty.lines
    else:
        transcript = [f"[{args.task}] arm={args.arm} phase={args.phase}"]
        print(transcript[0])
        doc = run_task(args.task, args.arm, phase=args.phase, repeat=args.repeat,
                       log=lambda m: (print(m), transcript.append(m)))
        transcript.append(f"stop={doc['stop_reason']} verified_fix={doc['verified_fix']} attempts={doc['attempts']} "
                          f"configs={doc['configs_used']} cost=${doc['cost_usd']:.4f} run_id={doc['run_id']}")
        print(transcript[-1])
    if args.save_dir:
        out = Path(args.save_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{doc['run_id']}.json").write_text(json.dumps(
            {**doc, "budget": BUDGET, "model": os.environ.get("CODING_MODEL")}, indent=1, default=str) + "\n")
        (out / f"{doc['run_id']}.txt").write_text("\n".join(transcript) + "\n")


if __name__ == "__main__":
    main()
