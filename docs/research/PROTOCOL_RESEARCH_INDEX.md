# ChairPlay protocol research: public index and findings

**Evidence boundary:** This is a *summary* of read-only, private iOS/Windows research, not a redistribution of third-party iOS binaries or disassembly. Source reports and full test artifacts remain in `CaneTLOTW/M.I.B._Research` with their original permissions.

## P5: display refresh / event responses

The original [P5 research branch](https://github.com/CaneTLOTW/M.I.B._Research/tree/work/chairplay-p5-protocol-research-20261107) examined `updateInfo`, `updateDisplayInfo`, event reply/CSeq handling and native iOS structures. Neither a selective Type111 refresh nor an actual zoom reread was established. Even a received status/ACK must not be interpreted as visible zoom. Full reconnect remained the observed native scaling positive control.

## P6: selective 111 vs predeclared ViewAreas

The [P6 research branch](https://github.com/CaneTLOTW/M.I.B._Research/tree/work/chairplay-ios27-final-comparison-issue181) found no substantiated receiver-originated mechanism that selectively tears down and renegotiates Stream111 with a new zoom while Stream110 stays up. Predeclared `viewAreas` were the practical **layout** candidate, not a proven native zoom mechanism. The resulting P6 guarded implementation is included in fork `main`.

The separate [P6 acceptance record](https://github.com/CaneTLOTW/M.I.B._Research/tree/work/chairplay-issue178-acceptance-20261108) documented sampled local Windows/iPhone View 0→1→2→0 and rapid 0→1→2 operation with command sends and screenshots. It did **not** independently isolate iPhone-rendered geometry from different scene/URL/overlay content or prove corresponding iOS ACKs. Result: CI and scoped local control observations passed, but **LIVE_UNVERIFIED** for protocol/visual causality and native ZoomFactor.

## P7: per-area zoom

[P7 PR #180](https://github.com/CaneTLOTW/M.I.B._Research/pull/180) built successfully in [experimental Windows CI](https://github.com/CaneTLOTW/M.I.B._Research/actions/runs/42426831167). The later [iOS 27.2 ViewArea analysis branch](https://github.com/CaneTLOTW/M.I.B._Research/tree/work/chairplay-ios27-final-comparison-issue181) found **no demonstrated** read of `viewAreas[i].zoomFactor` into a live scaling state in the examined paths, but source/observer coverage was incomplete. Formal status: `UNKNOWN_DUE_TO_SOURCE_GAP` and `LIVE_UNVERIFIED / DEFERRED`. This explains why P7 was not part of the native P6 merge.

## P8: panel removal and re-add

P8 is a **different hypothesis**: removing Type111 from `displayPanels` and re-adding it with new zoom/physical dimensions to elicit an iPhone-originated 111 TEARDOWN and fresh SETUP without interrupting 110. The Unit-side patch is [archived in this fork](../../contrib/mib2-skoda/experiments/p8/). It is uncompiled and untested. Success requires the actual 111 TEARDOWN/SETUP, setup counter 1→2, uninterrupted 110 and **visible 100→70 zoom**. `LOCAL_SENT` or ACK alone proves none of these.

**Privacy/licensing:** Per-device screenshots/logs, raw iOS binaries and disassembly are intentionally not copied to the public ChairPlay fork.
