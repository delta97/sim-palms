# SimConnect spawn-and-disconnect spike (SPIKE-009)

Console app that answers the SPIKE-005 questions on the sim PC. It was written on a machine without the MSFS SDK and has
**never been compiled**. Expect to fix member names on the first build; every unconfirmed one carries a `// VERIFY:` comment in
`Program.cs`. Note each fix in `docs/findings/SPIKE-005.md`.

## Build

Needs the .NET 8 SDK and the MSFS 2024 SDK (managed `Microsoft.FlightSimulator.SimConnect.dll` and native `SimConnect.dll`).

```powershell
cd spikes\simconnect-persist
dotnet build -c Release -p:MsfsSdk="C:\MSFS 2024 SDK"
```

`MsfsSdk` defaults to the `MSFS_SDK` environment variable (VERIFY the name; SPIKE-001 records it). The DLL subfolders default to
`SimConnect SDK\lib\managed` and `SimConnect SDK\lib` under it (VERIFY). If they differ, override them:
`-p:SimConnectManagedDir="<folder>" -p:SimConnectNativeDir="<folder>"`.

Output: `bin\Release\net8.0-windows\win-x64\SimConnectPersist.exe` or `bin\Release\net8.0-windows\SimConnectPersist.exe`
(depends on the SDK's platform handling). `spawned.json` is written to the current directory.

## Run

Start MSFS 2024 and load into a free flight first. Use a title from an installed SimObject (VERIFY; SPIKE-005 says where to look).

| Mode | Example | SPIKE-005 question it answers |
|---|---|---|
| `badtitle` | `SimConnectPersist badtitle` | What happens with a title that does not exist: exception, exception event, text? (step 3) |
| `spawn` | `SimConnectPersist spawn --title "<title>" --lat 32.7336 --lon -117.1897 --heading 0 --hold-s 60` | Does create work; request-to-id latency; does the object sit on the terrain at that lat/lon; which init-position settings work; which message pump works (steps 4, 11) |
| `spawn`, let it exit | same command; look after it closes | Does the object survive a clean disconnect? (step 5) |
| `remove` | `SimConnectPersist remove --ids-file spawned.json` | Can a new connection remove an old object by its old id? (step 6) |
| `spawn --crash` | `SimConnectPersist spawn --title "<title>" --lat ... --lon ... --crash` | Does the object survive the client process dying? (step 7). Then run `remove` again. |
| `spawn`, no remove | spawn, reload the flight or go to the main menu and back | Does it survive main menu / new flight? (step 8) |
| `spawn --count 100` | `SimConnectPersist spawn --title "<title>" --lat ... --lon ... --count 100 --spacing-m 10 --hold-s 30` | Total time for 100 creations, errors, frame rate by eye (step 9) |

Scaling (step 10): the C docs show no scale parameter for the create call, so the app does not try to scale. Record anything else you find.

Options: `--heading` degrees true (default 0); `--spacing-m` spacing between objects along an east-west line (default 10);
`--hold-s` seconds to wait before closing (default 30); `--crash` kills the process without closing the connection.
Console output is timestamped; save it for `docs/findings/SPIKE-005/<step>.log` (for example `... | Tee-Object step4.log`).

## Message pump

The app passes an `EventWaitHandle` to the `SimConnect` constructor and calls `ReceiveMessage()` when it is signalled. If no open
event arrives, switch to a window-message pump (hidden form plus user message id); `Connect()` has the recipe in a comment.
Record which one worked.
