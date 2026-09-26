# Gate 8 results — provenance

| Item | Value |
|---|---|
| Frozen code | `26b79a7` |
| Frozen memory | mem-v1 content sha256 `c701ea5ef355eb7bce1195498978532cf1003b5bfc368b2f4a03173899646bce` (4 checkpoints; `scripts/snapshot_hash.py`) |
| Pre-registration | `67bc540` (SPEC §13.4; docs + `.gitignore` only, code identical to `26b79a7`) |
| Protocol | 4 eval tasks × 3 arms × 5 repeats = 60 runs; attempt 1 shared across arms within a repeat, fresh per repeat; 5 sequential `scripts/run_suite.py --split eval --phase eval` runs |
| Run window | 2026-09-26, 17:35–17:45 UTC (run ids end in the timestamps below) |
| After the run | mem-v1 hash re-checked unchanged; no code, test or memory changes |

Every run, attempt, decision and model call is also in MongoDB (`reflex.runs`, `attempts`,
`decisions`, `calls`, `phase: "eval"`), keyed by the run ids in `runs/*.json`.

`report.txt` was produced by a read-only analysis script (not part of the harness) that reads the
`runs` and `decisions` rows. The semantic margins in it are recomputed from each memory run's
logged query narrative (`decisions.narrative`) against the frozen mem-v1, as pre-registered.

## Files (sha256)

```
0aa6e13b6875f59585ef6fe4011bbbbb5d043abc17367eb262b48be2315620a8  report.txt
161299d75229cad57ca05970c4e73b631bf77419d9b3b734ccf544ebc21740ea  index.txt
9f213ab351185bed593fb1ab2d1e11eebfe3088a70b7ce5578f9b2e2dd1f85de  repeat-1.log
b330fe75560209abf888e5cc528dbee573a6ea07abe02a2939bc295415411c85  repeat-2.log
9e842b70508dd947c72d590c314ee9401c3356cfafd2c9d23ab49b9238d36840  repeat-3.log
508ec89d9da683150feee080d79c222afa4809992e869430bc9517a137668d46  repeat-4.log
1c367ca868d5026ccc53e1570b3b4264bfc7bbe30e194600fb356920c41e3668  repeat-5.log
850ebf1069f27f940c49a634a7b1112d953c2767daf635fe61c63de148bd44a1  runs/suite-eval-20260926T173508.json
e23926540a46c4138ff39b0462de83c4398590b2383005c7691c82fa451f4101  runs/suite-eval-20260926T173715.json
a83710c11770d5234fa247f3e49911308db2e6485b92a53bcbd1e169c26108b6  runs/suite-eval-20260926T173901.json
dc9c76bdfab966c5317b69a0c572fd6945bff491c6625e0c1d5ae8cc7b8fcdc3  runs/suite-eval-20260926T174056.json
d0c731be0f936ea32373c0567c3dc8dbec6b342ab3bf8520226e3f772a51a123  runs/suite-eval-20260926T174311.json
```

`index.txt` maps repeat number → suite file. `repeat-N.log` is the console output of each repeat.

## Chart (Phase 0, after the results commit)

`results/gate8/make_chart.py` renders `docs/gate8_results.png` from `report.txt` only (read-only,
no model calls): `python results/gate8/make_chart.py` with the repo venv (matplotlib 3.11.2).
Output is deterministic in that environment (same hash on repeated runs). An earlier render made
in a different matplotlib/font environment differed by 1–2 px in size with identical numbers; it
was replaced by the version regenerated here. Panel 3 was later redesigned (one stacked bar:
plain retry on family A — 9 hacks that passed visible tests and failed hidden tests, 1 failed
visible tests, 0 actually fixed); the hashes below are for that version. Data files unchanged.

```
390e392a1f45e926c6b5a7fe373ba5d799ccdeadd433a5748016041b0c881b02  ../../docs/gate8_results.png
81b9771df2c7078631f2cc1cf58e31a83c3e4a7eae66912e6fb0ad66f41ceabf  make_chart.py
```

