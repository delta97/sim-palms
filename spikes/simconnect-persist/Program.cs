// SPIKE-009: SimConnect spawn-and-disconnect spike. Answers the SPIKE-005 questions.
// Written without the SDK present: it has never been compiled. Every member name marked VERIFY must be
// checked against Microsoft.FlightSimulator.SimConnect.dll (SPIKE-005 step 1); managed names can differ from the C API.
// Docs for the C call: https://docs.flightsimulator.com/msfs2024/retail/programming-apis/simconnect/api-reference/ai-object/simconnect_aicreatesimulatedobject_ex1/
using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Microsoft.FlightSimulator.SimConnect; // VERIFY: namespace of the managed wrapper

namespace SimConnectPersist;

// Request ids are base + index, cast to this enum for the managed API (VERIFY: it takes an Enum for the request id).
internal enum Req : uint { CreateBase = 1000, RemoveBase = 5000 }

internal sealed record Spawned(string title, uint[] ids, string created_utc);

internal static class Program
{
    private static SimConnect? _sc;
    private static readonly EventWaitHandle _signal = new(false, EventResetMode.AutoReset);
    private static readonly Stopwatch _clock = Stopwatch.StartNew();
    private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    // request id -> time the create call was sent (ms on _clock); read in the assigned-id handler.
    private static readonly Dictionary<uint, double> _sentAt = new();
    private static readonly List<(uint req, uint objId, double latencyMs)> _assigned = new();
    private static readonly List<string> _errors = new();
    private static bool _opened, _quit;

    private static int Main(string[] args)
    {
        if (args.Length == 0) return Usage();
        var o = ParseOptions(args.Skip(1).ToArray());
        try
        {
            return args[0] switch
            {
                "spawn" => Spawn(o),
                "remove" => Remove(o),
                "badtitle" => BadTitle(o),
                _ => Usage(),
            };
        }
        catch (Exception ex)
        {
            // Includes COMException thrown by the managed wrapper for failed calls. Type and HResult are findings.
            Log($"FATAL {ex.GetType().FullName}: {ex.Message} (HResult 0x{ex.HResult:X8})");
            return 1;
        }
    }

    // ---- modes -------------------------------------------------------------------------------------------------

    // SPIKE-005 steps 4, 5, 7, 8, 9, 10: spawn, latency, clean disconnect vs crash, many objects.
    private static int Spawn(Dictionary<string, string> o)
    {
        var title = Opt(o, "title") ?? throw new ArgumentException("--title is required");
        var lat = double.Parse(Opt(o, "lat") ?? throw new ArgumentException("--lat is required"), Inv);
        var lon = double.Parse(Opt(o, "lon") ?? throw new ArgumentException("--lon is required"), Inv);
        var heading = double.Parse(Opt(o, "heading") ?? "0", Inv);
        var count = int.Parse(Opt(o, "count") ?? "1", Inv);
        var spacingM = double.Parse(Opt(o, "spacing-m") ?? "10", Inv);
        var holdS = double.Parse(Opt(o, "hold-s") ?? "30", Inv);
        var crash = o.ContainsKey("crash");

        Connect();

        var t0 = _clock.Elapsed.TotalMilliseconds;
        for (var i = 0; i < count; i++)
        {
            // Spread along an east-west line: metres to degrees (1 deg lat ~ 111,320 m; longitude scaled by cos(lat)).
            var dLon = i * spacingM / (111_320.0 * Math.Cos(lat * Math.PI / 180.0));

            // VERIFY: struct name and field names against the managed DLL. The C struct SIMCONNECT_DATA_INITPOSITION
            // has Latitude, Longitude, Altitude, Pitch, Bank, Heading (doubles), OnGround and Airspeed (DWORDs).
            var pos = new SIMCONNECT_DATA_INITPOSITION
            {
                Latitude = lat,
                Longitude = lon + dLon,
                Altitude = 0,      // VERIFY: meaning when OnGround = 1 (feet MSL or AGL?); SPIKE-005 checks whether it sits on terrain.
                Pitch = 0,
                Bank = 0,
                Heading = heading, // VERIFY: degrees true vs magnetic for INITPOSITION.Heading
                OnGround = 1,      // VERIFY: uint vs bool in the managed struct; 1 = on ground per the C struct docs
                Airspeed = 0,
            };

            var reqId = (uint)Req.CreateBase + (uint)i;
            _sentAt[reqId] = _clock.Elapsed.TotalMilliseconds;

            // VERIFY: managed method name and signature. The C call is
            // SimConnect_AICreateSimulatedObject_EX1(hSimConnect, szContainerTitle, szLivery, InitPos, RequestID).
            // The 2020 managed wrapper has AICreateSimulatedObject(title, InitPos, RequestID) with no livery; the 2024
            // wrapper may add an _EX1 overload. If only the non-EX1 one exists, record that as a finding.
            _sc!.AICreateSimulatedObject_EX1(title, "", pos, (Req)reqId);
            Log($"create req={reqId} title='{title}' lat={pos.Latitude:F7} lon={pos.Longitude:F7} onGround={pos.OnGround} alt={pos.Altitude} sent");

            // Dispatch pending messages between sends so latency is not inflated by our own queueing.
            Pump(TimeSpan.FromMilliseconds(1));
        }

        // Wait for all assigned ids, up to 30 s.
        Pump(TimeSpan.FromSeconds(30), () => _assigned.Count + _errors.Count >= count);
        var totalMs = _clock.Elapsed.TotalMilliseconds - t0;

        foreach (var a in _assigned.OrderBy(a => a.req))
            Log($"RESULT req={a.req} objectId={a.objId} latency_ms={a.latencyMs:F1}");
        Log($"RESULT requested={count} assigned={_assigned.Count} errors={_errors.Count} total_ms={totalMs:F1}");

        var ids = _assigned.OrderBy(a => a.req).Select(a => a.objId).ToArray();
        var rec = new Spawned(title, ids, DateTime.UtcNow.ToString("o"));
        var json = JsonSerializer.Serialize(rec, new JsonSerializerOptions { WriteIndented = true });
        var stamped = $"spawned-{DateTime.UtcNow:yyyyMMdd-HHmmss}.json"; // kept, so earlier runs' ids are not lost
        File.WriteAllText(stamped, json);
        File.WriteAllText("spawned.json", json); // latest run; default input of `remove`
        Log($"wrote {stamped} and spawned.json");
        var exitCode = _assigned.Count == 0 || _errors.Count > 0 ? 1 : 0;

        Log($"holding {holdS:F0} s (look at the spot now)...");
        Pump(TimeSpan.FromSeconds(holdS));

        if (crash)
        {
            // SPIKE-005 step 7: die without closing the connection.
            Log("CRASH: Environment.FailFast without closing the connection");
            Environment.FailFast("SPIKE-009 deliberate crash");
        }

        Log("closing connection cleanly");
        Disconnect();
        Log("closed; process exiting. Check whether the objects stay.");
        return exitCode;
    }

    // SPIKE-005 steps 6 and 7 (remove after crash): a NEW connection removes objects by the OLD ids.
    private static int Remove(Dictionary<string, string> o)
    {
        var file = Opt(o, "ids-file") ?? "spawned.json";
        var rec = JsonSerializer.Deserialize<Spawned>(File.ReadAllText(file)) ?? throw new InvalidDataException(file);
        Log($"loaded {rec.ids.Length} ids from {file} (created {rec.created_utc}, title '{rec.title}')");

        Connect();
        for (var i = 0; i < rec.ids.Length; i++)
        {
            var id = rec.ids[i];
            try
            {
                // VERIFY: managed method name and signature. C: SimConnect_AIRemoveObject(hSimConnect, ObjectID, RequestID).
                _sc!.AIRemoveObject(id, (Req)((uint)Req.RemoveBase + (uint)i));
                Log($"remove objectId={id} sent (no exception from the call)");
            }
            catch (Exception ex)
            {
                Log($"remove objectId={id} EXCEPTION {ex.GetType().Name}: {ex.Message} (HResult 0x{ex.HResult:X8})");
            }
            // An invalid id may only show up as an OnRecvException event shortly after the call.
            Pump(TimeSpan.FromMilliseconds(500));
        }
        Pump(TimeSpan.FromSeconds(2));
        Log($"RESULT remove_calls={rec.ids.Length} exception_events={_errors.Count}");
        Disconnect();
        return _errors.Count > 0 ? 1 : 0;
    }

    // SPIKE-005 step 3: what does a non-existent title do?
    private static int BadTitle(Dictionary<string, string> o)
    {
        const string bad = "PalmSpike Does Not Exist";
        var lat = double.Parse(Opt(o, "lat") ?? "0", Inv);
        var lon = double.Parse(Opt(o, "lon") ?? "0", Inv);
        Connect();
        var pos = new SIMCONNECT_DATA_INITPOSITION { Latitude = lat, Longitude = lon, Altitude = 0, Heading = 0, OnGround = 1, Airspeed = 0 };
        var reqId = (uint)Req.CreateBase;
        _sentAt[reqId] = _clock.Elapsed.TotalMilliseconds;
        try
        {
            _sc!.AICreateSimulatedObject_EX1(bad, "", pos, (Req)reqId); // VERIFY: same member as in Spawn
            Log($"create with title '{bad}' returned without exception; waiting for events");
        }
        catch (Exception ex)
        {
            Log($"create with title '{bad}' EXCEPTION {ex.GetType().FullName}: {ex.Message} (HResult 0x{ex.HResult:X8})");
        }
        Pump(TimeSpan.FromSeconds(10), () => _assigned.Count + _errors.Count > 0);
        Log($"RESULT assigned={_assigned.Count} exception_events={_errors.Count}");
        foreach (var a in _assigned) Log($"RESULT unexpectedly got objectId={a.objId}");
        Disconnect();
        return 0;
    }

    // ---- connection and message pump ---------------------------------------------------------------------------

    private static void Connect()
    {
        // VERIFY: constructor signature SimConnect(string name, IntPtr hWnd, uint userEventWin32, WaitHandle handle, uint configIndex).
        // Wait-handle approach: no window needed. If events never arrive with the handle, SPIKE-005 should try a
        // window-message pump instead (add <UseWindowsForms>true</UseWindowsForms> to the csproj): create a hidden WinForms Form, pass its Handle and a user message id (for example
        // WM_USER_SIMCONNECT = 0x0402) to the constructor, override WndProc, and when m.Msg equals that id call _sc.ReceiveMessage().
        _sc = new SimConnect("PalmSpike", IntPtr.Zero, 0, _signal, 0);

        // VERIFY: event names on the managed class (OnRecvOpen, OnRecvQuit, OnRecvException, OnRecvAssignedObjectId).
        _sc.OnRecvOpen += (s, d) =>
        {
            _opened = true;
            // VERIFY: field names on SIMCONNECT_RECV_OPEN
            Log($"EVENT open: app='{d.szApplicationName}' ver={d.dwApplicationVersionMajor}.{d.dwApplicationVersionMinor} build={d.dwApplicationBuildMajor}.{d.dwApplicationBuildMinor} simconnect={d.dwSimConnectVersionMajor}.{d.dwSimConnectVersionMinor}");
        };
        _sc.OnRecvQuit += (s, d) => { _quit = true; Log("EVENT quit (sim is closing the connection)"); };
        _sc.OnRecvException += (s, d) =>
        {
            // VERIFY: SIMCONNECT_RECV_EXCEPTION fields dwException, dwSendID, dwIndex and the SIMCONNECT_EXCEPTION enum name
            var text = $"EVENT exception: {(SIMCONNECT_EXCEPTION)d.dwException} ({d.dwException}) sendId={d.dwSendID} index={d.dwIndex}";
            _errors.Add(text);
            Log(text);
        };
        _sc.OnRecvAssignedObjectId += (s, d) =>
        {
            // VERIFY: SIMCONNECT_RECV_ASSIGNED_OBJECT_ID fields dwRequestID, dwObjectID
            var now = _clock.Elapsed.TotalMilliseconds;
            var lat = _sentAt.TryGetValue(d.dwRequestID, out var t) ? now - t : double.NaN;
            _assigned.Add((d.dwRequestID, d.dwObjectID, lat));
            Log($"EVENT assigned-object-id: req={d.dwRequestID} objectId={d.dwObjectID} latency_ms={lat:F1}");
        };

        Log("connecting as 'PalmSpike'; waiting for open event...");
        Pump(TimeSpan.FromSeconds(15), () => _opened);
        if (!_opened)
            throw new TimeoutException("No open event within 15 s. Is the sim running and in a flight? Try the window-message pump (see Connect).");
    }

    private static void Disconnect()
    {
        _sc?.Dispose(); // VERIFY: Dispose() is how the managed wrapper closes (C: SimConnect_Close).
        _sc = null;
    }

    // Wait on the handle and dispatch; stops at the timeout or when `done` returns true.
    // ReceiveMessage() invokes the On* handlers registered in Connect().
    private static void Pump(TimeSpan span, Func<bool>? done = null)
    {
        var end = _clock.Elapsed + span;
        while (_clock.Elapsed < end && !_quit)
        {
            if (done?.Invoke() == true) return;
            var remainingMs = (end - _clock.Elapsed).TotalMilliseconds;
            if (remainingMs <= 0) break;
            // Clamp the wait so short pumps (the 1 ms one between creates) do not stall for 100 ms.
            _signal.WaitOne((int)Math.Max(1, Math.Min(100, remainingMs)));
            // Dispatch on signal AND on timeout: a missed or coalesced signal must not strand queued messages.
            // VERIFY: ReceiveMessage() may dispatch only one message per call, so drain a few times per wake.
            for (var k = 0; k < 8; k++) Receive();
        }
    }

    private static void Receive()
    {
        try { _sc?.ReceiveMessage(); } // VERIFY: method name; it can throw COMException on a broken connection
        catch (Exception ex) { Log($"ReceiveMessage EXCEPTION {ex.GetType().Name}: {ex.Message} (HResult 0x{ex.HResult:X8})"); }
    }

    // ---- helpers -----------------------------------------------------------------------------------------------

    private static void Log(string msg) =>
        Console.WriteLine($"{DateTime.UtcNow:HH:mm:ss.fff}Z [{_clock.Elapsed.TotalMilliseconds,9:F1} ms] {msg}");

    private static Dictionary<string, string> ParseOptions(string[] a)
    {
        var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < a.Length; i++)
        {
            if (!a[i].StartsWith("--")) continue;
            var key = a[i][2..];
            // Negative numbers (longitudes) start with a single '-', so only "--" marks the next option.
            d[key] = i + 1 < a.Length && !a[i + 1].StartsWith("--") ? a[++i] : "true";
        }
        return d;
    }

    private static string? Opt(Dictionary<string, string> o, string k) => o.TryGetValue(k, out var v) ? v : null;

    private static int Usage()
    {
        Console.WriteLine("SimConnectPersist (SPIKE-009)");
        Console.WriteLine("  spawn --title T --lat D --lon D [--heading D] [--count N] [--spacing-m M] [--hold-s S] [--crash]");
        Console.WriteLine("  remove --ids-file spawned.json");
        Console.WriteLine("  badtitle [--lat D --lon D]");
        return 2;
    }
}
