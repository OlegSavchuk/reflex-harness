"""python -m reflex_harness run --task X --arm memory [--phase dev]"""
import argparse

from .controller import ARMS, run_task


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reflex_harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--task", required=True)
    r.add_argument("--arm", choices=ARMS, default="memory")
    r.add_argument("--phase", choices=("dev", "eval"), default="dev")
    r.add_argument("--repeat", type=int, default=0, help="repeat index (seeds the random arm)")
    args = ap.parse_args(argv)
    print(f"[{args.task}] arm={args.arm} phase={args.phase}")
    doc = run_task(args.task, args.arm, phase=args.phase, repeat=args.repeat)
    print(f"stop={doc['stop_reason']} verified_fix={doc['verified_fix']} attempts={doc['attempts']} "
          f"configs={doc['configs_used']} cost=${doc['cost_usd']:.4f} run_id={doc['run_id']}")


if __name__ == "__main__":
    main()
