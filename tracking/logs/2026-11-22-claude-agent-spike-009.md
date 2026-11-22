# Session log: 2026-11-22, claude-agent, spike-009

- **Started / ended:** 2026-11-22 (single session)
- **Agent / model / person:** claude-agent (simconnect-dotnet-engineer role)
- **Branch / worktree:** task/spike-009-write-the-simconnect-spawn-and-disconnec, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SPIKE-009
- **Tasks:** SPIKE-009 (in_progress -> review)

## Goal

Write the single-file .NET 8 console app that SPIKE-005 runs on the sim PC to answer the SimConnect spawn and disconnect questions.

## What changed

- `spikes/simconnect-persist/Program.cs`: modes `spawn`, `remove`, `badtitle`; event-wait-handle message pump; handlers for open, quit, exception, assigned-object-id (fa9a45b)
- `spikes/simconnect-persist/SimConnectPersist.csproj`: net8.0-windows x64, `MsfsSdk` property, managed DLL reference, native DLL copy (fa9a45b)
- `spikes/simconnect-persist/README.md`, `.gitignore`: build and run commands, mode-to-question table (fa9a45b)

## Verification

- `ls`, `grep -cE "spawn|remove|badtitle"` = 15, `grep -c VERIFY` = 16.
- Build not run: no .NET SDK in this environment. The code has never been compiled.

## Decisions and findings

- Only the C API page for `SimConnect_AICreateSimulatedObject_EX1` was used; every managed-wrapper name is a `VERIFY:`.
- The 2020 managed wrapper has no livery argument on the create call; whether 2024 has an `_EX1` overload is unknown. Code assumes it does.

## Open issues

- Reviewer acceptance criterion unticked (needs a reviewer).
- Compile errors on first build are expected (SPIKE-005 step 1).

## Handoff: next steps

1. Review SPIKE-009 against the SPIKE-005 question list.
2. On the sim PC, run SPIKE-005 step 1: `dotnet build -c Release -p:MsfsSdk="<SDK path>"` in `spikes\simconnect-persist`, fix names, record each fix.
