# SPIKE-001 findings: SDK install and empty Dev Mode project (in progress)

- **Date:** 2026-11-22
- **Sim version:** 1.9.24.0 (Steam edition, app 2537590, Steam buildid 26385953; read from the sim's own crash report, `BuildID "1.9.24.0"`, branch `LIVE1.0`; still to confirm on screen)
- **SDK version:** 1.8.2 (Core), `C:\MSFS 2024 SDK\version.txt` = `1.8.2` / `2634044`; Windows uninstall entry "Microsoft Flight Simulator 2024 SDK 1.8.2 (Core)", installed 2026-11-22
- **Status:** steps 1-6 done by the user; steps 7-11 not done (the sim crashed right after the project was created). Paths below were read from disk by the integrator, not assumed.

## Results table

| Item | Result |
|---|---|
| Date | 2026-11-22 |
| Sim version | 1.9.24.0 (from crash report; on-screen check pending) |
| SDK version | 1.8.2 (Core) |
| Dev Mode menu path | not recorded yet (Dev Mode was on: crash report `DevMode=1`) |
| SDK install folder | `C:\MSFS 2024 SDK\` (subfolders: Licenses, LodProcessingPresets, ModelBehaviorDefs, Schemas, SharedAssets, SimConnect SDK, Tools, WASM) |
| Environment variable set by installer | `MSFS2024_SDK=C:\MSFS 2024 SDK\` (machine scope). No `MSFS_SDK`. |
| `fspackagetool.exe` path; on PATH? | `C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`; **not** on PATH (call it by full path) |
| SimConnect managed DLL path | `C:\MSFS 2024 SDK\SimConnect SDK\lib\managed\Microsoft.FlightSimulator.SimConnect.dll` (172,032 bytes) |
| SimConnect native DLL path | `C:\MSFS 2024 SDK\SimConnect SDK\lib\SimConnect.dll` (84,480 bytes) |
| Project folder | `C:\Users\colep\OneDrive\Documents\MyFSProjects\palmfix-spike\` (the editor's default location; inside OneDrive) |
| Project Editor steps to create the project (numbered) | not recorded yet |
| Empty project build: ok / error text | **not built**: the project has no package yet (`<Packages/>`) and no build output folders |
| Build output folder | none yet; the project file sets `<OutputDirectory>.</OutputDirectory>`, `<TemporaryOutputDirectory>_PackageInt</TemporaryOutputDirectory>`, `FolderName="Packages"`, `MetadataFolderName="PackagesMetadata"` |
| Name `palmfix-spike` accepted and built? | accepted (project saved with `Name="palmfix-spike"`); not built yet |
| Project reopens after restart? | not checked yet |

## What happened

1. The user turned on Dev Mode, installed SDK 1.8.2 and created project `palmfix-spike` in the Project Editor.
2. The editor wrote `palmfix-spike.xml` and `palmfix-spike.xml.user` at 14:43:07 local time. The project file:

   ```xml
   <Project Version="2" Name="palmfix-spike" FolderName="Packages" MetadataFolderName="PackagesMetadata">
       <OutputDirectory>.</OutputDirectory>
       <TemporaryOutputDirectory>_PackageInt</TemporaryOutputDirectory>
       <Packages/>
       <PublishingGroups/>
   </Project>
   ```

3. **The sim crashed 25 s later (14:43:32).** Windows Application log: `FlightSimulator2024.exe` 1.9.24.0, first exception `0xe06d7363` (C++ exception) in KERNELBASE.dll, then `0xc0000005` (access violation) in ntdll.dll. The sim's `AsoboReport-Crash.txt` says `Msg="WinMain"`, `Type="SEH"`, `DevMode=true`; `crashdata.txt` says session state `GAME_WORLDMAP / WORLDMAP_HOMEPAGE`, not in flight, 212 s into the session. Two crash dumps (~250 MB each) are in `%LOCALAPPDATA%\CrashDumps\`. The cause is not identified; the project creation is the most likely trigger by timing, not proven.
4. Nothing was lost: the project file survived, it is just empty (no package added yet).

## Other checks done from the repo

- The SPIKE-009 SimConnect console app (`spikes/simconnect-persist/`) **builds against this SDK with 0 warnings and 0 errors**
  (`dotnet build -c Release`, .NET 8.0.428), which confirms at compile level the managed SimConnect API names it uses. Its `.csproj`
  now defaults to `MSFS2024_SDK`. Runtime behaviour is still for SPIKE-005.

## Still to do (user, in the sim)

1. Reopen the sim, turn on Dev Mode, reopen `palmfix-spike` (record the menu path and whether it reopened cleanly: rows "Dev Mode menu path", "Project reopens after restart?").
2. Add a package and a scenery asset group (step 7; write each click down).
3. Build the project (step 8) and note the result and output folder.
4. If it crashes again at the same point, note what you clicked last; a second crash at the same step is a finding for RISK-005.

After the build, an agent records the tree listing (step 9) and finishes this note.

Note: the project sits inside OneDrive (`Documents\MyFSProjects`). Build output (`Packages\`, `_PackageInt\`) will sync to
OneDrive and sync can lock files mid-build. If a build fails with file-in-use errors, move the project to a local folder such
as `C:\palmfix\palmfix-spike\` (the runbook's suggestion). VERIFY on the first build.
