# Dock Benchmark Workspace

This folder contains reproducible real-app compatibility checks for `ldocking`.

## Trusted sources used

- `third_party/dock_benchmarks/pyside-setup`: official Qt for Python examples.
  - benchmark target: `examples/widgets/mainwindows/dockwidgets/dockwidgets.py`
- `third_party/dock_benchmarks/labelme`: mature open-source Qt app with multiple `QDockWidget`s.
  - current use in this repo: static dock-layout inspection only

## Commands

Official example, native Qt:

```bash
python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode native
```

Official example, monkeypatched:

```bash
python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode monkey
```

Official example, scripted replay:

```bash
python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode native --scenario replay
python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode monkey --scenario replay
```

Local labelme-shape fixture benchmark:

```bash
python tools/dock_benchmarks/benchmark_local_fixture.py --fixture labelme_shape_app --mode native --scenario replay
python tools/dock_benchmarks/benchmark_local_fixture.py --fixture labelme_shape_app --mode monkey --scenario replay
```

Local qtpy-style import fixture benchmark:

```bash
python tools/dock_benchmarks/benchmark_local_fixture.py --fixture qtpy_style_app --mode native
python tools/dock_benchmarks/benchmark_local_fixture.py --fixture qtpy_style_app --mode monkey
```

Static inspection of labelme's dock layout:

```bash
python tools/dock_benchmarks/inspect_labelme_docks.py
```

Artifacts from the runnable benchmark are written to `tools/dock_benchmarks/artifacts/`.

## Findings from this pass

- Official Qt dockwidgets example exposed a real mismatch in `ldocking` before the fix:
  native Qt kept the two right-side docks as separate docks in the same area, while `ldocking`
  auto-tabified them whenever `AllowTabbedDocks` was enabled.
- That behavior was not Qt-compatible. The fix in this repo changes default same-area
  `addDockWidget()` behavior to split-by-default and reserve tabbing for:
  explicit `tabifyDockWidget()`, center tab drops, and `ForceTabbedDocks`.
- The same compatibility risk exists structurally in `labelme`, which adds four docks to
  `Qt.RightDockWidgetArea` in sequence. Without the fix, those docks would have collapsed into
  tabs under the monkeypatch instead of the native multi-dock side layout.
- `labelme` runtime benchmarking is deferred in this environment because it imports `PyQt5`
  directly and also needs extra app dependencies (`imgviz`, `natsort`, others) that are not part
  of this repo's normal PySide6 benchmark setup.

## Follow-up targets

- Add a PySide6/qtpy-capable real app as the next runnable benchmark beyond the official example.
- If a qtpy-based trusted app is added, keep the monkeypatch preload path import-first and avoid
  app-specific source edits.
- Keep the local labelme-shape and qtpy-style fixtures in sync with real monkeypatch regressions so
  every real-app finding has a small reproducible benchmark counterpart.
