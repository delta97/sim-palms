# SPIKE-001 findings: SDK install and empty Dev Mode project

- **Date:** 2026-11-22
- **Sim version:** 1.9.24.0 (Steam edition, app 2537590, Steam buildid 26385953; read from the sim's own crash report, `BuildID "1.9.24.0"`, branch `LIVE1.0`; still to confirm on screen)
- **SDK version:** 1.8.2 (Core), `C:\MSFS 2024 SDK\version.txt` = `1.8.2` / `2634044`; Windows uninstall entry "Microsoft Flight Simulator 2024 SDK 1.8.2 (Core)", installed 2026-11-22
- **Status:** the empty project with one scenery package **built cleanly** (user, 14:55-14:56). Paths and files below were read from disk by the integrator, not assumed. Still open: the Dev Mode menu path and the editor click steps (the user did them in the sim; Dev Mode freezes or crashes the sim on entry, see below). The on-screen sim version check is also still open.

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
| Project Editor steps to create the project (numbered) | not recorded (done by the user in the sim); the resulting files are captured in `SPIKE-001/captured/` |
| Empty project build: ok / error text | **ok**: `_PackageInt\_RPTErrors.xml` is `<RPTErrors/>` (no errors); output written 14:55:57 |
| Build output folder | `<project>\Packages\cole-palmfix\` (manifest.json, layout.json, bglIndex.bout, ContentInfo, `Scenery\palmfix\Scene\Scene.bgl`); intermediates in `<project>\_PackageInt\`; metadata in `<project>\PackagesMetadata\`. The build does **not** write into the sim's Community folder; it also **exported a zip** to `<export path>\Community\cole-palmfix.zip` (6,166 bytes, same 6 files as the output folder). The export path comes from Dev Mode settings: `%APPDATA%\Microsoft Flight Simulator 2024\DevMode.xml` `User_Export_Package_Path` (here set to the repo folder; `User_Export_Package_Mode` = 2). |
| Name `palmfix-spike` accepted and built? | yes: project `palmfix-spike` (lowercase + hyphen) and package `cole-palmfix` both built |
| Project reopens after restart? | yes in practice: the user reopened `palmfix-spike` after the 14:43 crash, added the package and built it at 14:55 |

## Confirmed file formats (captured in `SPIKE-001/captured/`, folder tree in `SPIKE-001/tree.txt`)

- **Project** `palmfix-spike.xml`: `<Project Version="2" Name=... FolderName="Packages" MetadataFolderName="PackagesMetadata">`, `<Packages><Package>PackageDefinitions\cole-palmfix.xml</Package></Packages>`.
- **Package definition** `PackageDefinitions\cole-palmfix.xml`: `<AssetPackage Version="0.1.0">` with `ContentType SCENERY`, `Title`, `Creator`,
  `PackageOrderHint CUSTOM_SCENERY_PATCH`, and two asset groups: `ContentInfo` (type `ContentInfo`, AssetDir
  `PackageDefinitions\cole-palmfix\ContentInfo`, OutputDir `ContentInfo\cole-palmfix`) and `Scene` (type `BGL`, AssetDir
  `PackageSources\Scenery\palmfix\Scene\`, OutputDir `Scenery\palmfix\Scene\`). This is `scene_dir` for plan 04.
- **Scene source** `PackageSources\Scenery\palmfix\Scene\Scene.xml`: empty `<FSData version="9.0"/>`, compiled to a 56-byte `Scene.bgl`.
  The compile schema is `C:\MSFS 2024 SDK\Toolsinglcomp.xsd` (also `bglcomp_gltfv1_1.xsd`).
- **manifest.json** (generated): `content_type SCENERY`, `package_version 0.1.0`, `minimum_game_version 1.9.24`,
  `minimum_compatibility_version 9.21.0.251`, `export_type Community`, `builder "Microsoft Flight Simulator 2024"`.
- The package's thumbnail is an SDK default (not copied into the repo).

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

5. The user reopened the project, added package `cole-palmfix` with a scenery asset group and built it at 14:55-14:56. The build is clean.
6. The user reports that entering Dev Mode often freezes and then crashes the sim. One crash is documented above; the cause is not known.

## Still open

1. Dev Mode menu path and the editor click steps were not written down (they are not needed to go on: the captured files are the reference).
2. **Dev Mode instability** (freeze/crash on entry, sim 1.9.24.0, SDK 1.8.2): track under RISK-005. Later spikes should prefer
   command-line builds (`fspackagetool`, SPIKE-004) and keep Dev Mode sessions short.

Note: the project sits inside OneDrive (`Documents\MyFSProjects`). Build output (`Packages\`, `_PackageInt\`) will sync to
OneDrive and sync can lock files mid-build. If a build fails with file-in-use errors, move the project to a local folder such
as `C:\palmfix\palmfix-spike\` (the runbook's suggestion). VERIFY on the first build.
