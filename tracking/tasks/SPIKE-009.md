---
id: SPIKE-009
title: Write the SimConnect spawn-and-disconnect spike console app (C#)
status: in_progress
phase: 0
area: SPIKE
kind: build
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: []
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [spikes/simconnect-persist/]
owner: claude-agent
branch: task/spike-009-write-the-simconnect-spawn-and-disconnec
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SPIKE-009"
updated: 2026-11-22
---

## Goal

A small, single-file .NET 8 console app in `spikes/simconnect-persist/` that the user can build and run on the sim PC to answer the SPIKE-005 questions: spawn a static SimObject on the ground, measure creation latency, disconnect cleanly or crash, and try to remove the object from a new connection.

## Context

- Phase 0 task 9 in `plans/05-phases.md` ("a 50-line C# SimConnect script"). The questions it must answer: `plans/detailed/04-fs2024-integration.md#spike-005-simconnect-spawn-test`. Expect 100-200 lines, because each question needs its own mode.
- API page: `SimConnect_AICreateSimulatedObject_EX1`, https://docs.flightsimulator.com/msfs2024/retail/programming-apis/simconnect/api-reference/ai-object/simconnect_aicreatesimulatedobject_ex1/ . VERIFY every managed-wrapper member name used against the DLL from the installed SDK (SPIKE-001 records the path); the managed names can differ from the C names.
- Written on Linux; it can't be compiled here because the managed SimConnect DLL ships only with the SDK. The first compile happens in SPIKE-005 step 1. Keep it simple enough to fix there.
- ASSET-070 reuses this app later with a palm SimObject title, so `--title` must be a parameter.
- Not `palmlive`. No shared code, no tests project.

## Steps

1. `spikes/simconnect-persist/SimConnectPersist.csproj`: `net8.0-windows`, `x64`, `OutputType Exe`, a `Reference` to `Microsoft.FlightSimulator.SimConnect.dll` with `HintPath` built from an `MsfsSdk` MSBuild property (default `$(MSFS_SDK)`; VERIFY the env var name and the DLL subfolder from SPIKE-001), and a `None Include` that copies the native `SimConnect.dll` to the output folder.
2. `spikes/simconnect-persist/Program.cs` with these modes:
   - `spawn --title T --lat D --lon D [--heading D] [--count N] [--spacing-m M] [--hold-s S] [--crash]`: connect (client name `PalmSpike`), create N objects on the ground (`OnGround = 1`, altitude 0; VERIFY the init-position struct fields), print each request time, assigned object id and latency in ms, write `spawned.json` (`title`, `ids`, `created_utc`), wait `--hold-s` (default 30), then either close the connection cleanly or, with `--crash`, call `Environment.FailFast` without closing.
   - `remove --ids-file spawned.json`: new connection; call the remove-object API for each id; print success or the exception or SimConnect exception event per id.
   - `badtitle`: try to create an object with title `PalmSpike Does Not Exist`; print what comes back (exception, exception event, error text).
3. Message pump: use an `EventWaitHandle` passed to the SimConnect constructor and call `ReceiveMessage()` when it is signalled, with a timeout loop. Comment where a window-message pump would be needed instead if the handle approach fails (VERIFY in SPIKE-005).
4. Subscribe to the open, quit, exception and assigned-object-id events; log each with a timestamp.
5. `spikes/simconnect-persist/README.md`: build command (`dotnet build -c Release -p:MsfsSdk="<SDK path>"`), each mode with an example, and the SPIKE-005 question each mode answers.

## Acceptance criteria

- [ ] `Program.cs` implements `spawn` (with `--count`, `--hold-s`, `--crash`), `remove` and `badtitle`.
- [ ] Every SimConnect type or member name the code relies on has a `// VERIFY:` comment unless it was checked against the SDK docs page (cite it).
- [ ] The README gives the exact build and run commands.
- [ ] A reviewer (simconnect-dotnet-engineer or code-reviewer) has read it against the SPIKE-005 question list and found every question covered.

## Verification

```bash
ls spikes/simconnect-persist/
grep -cE "spawn|remove|badtitle" spikes/simconnect-persist/Program.cs
grep -c "VERIFY" spikes/simconnect-persist/Program.cs
```

Compiling is checked on the sim PC in SPIKE-005 step 1. If `dotnet` is installed on Linux, `dotnet build` is expected to fail only on the missing SimConnect reference.

## Log

- 2026-11-22 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/spike-009-write-the-simconnect-spawn-and-disconnec worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SPIKE-009
