// ApiClient.cs
// Handles all HTTP communication with the Python backend at localhost:8000.
// Every method is a Coroutine — call with StartCoroutine() from any MonoBehaviour.

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;

public class ApiClient : MonoBehaviour
{
    
    // Change this if the backend runs on a different machine or port.
    private const string BASE_URL = "http://localhost:8000";
 
    // If the backend doesn't respond within this many seconds, we give up.
    private const int TIMEOUT_SECONDS = 5;
     
    
    public IEnumerator GetState(Action<StateResponse> onSuccess,
                                Action<string> onError = null)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/state");
        req.timeout = TIMEOUT_SECONDS;
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/state] {req.error}");
            yield break;
        }

        StateResponse result = null;
        try
        {
            result = JsonConvert.DeserializeObject<StateResponse>(req.downloadHandler.text);
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/state] Parse error: {e.Message}");
            yield break;
        }

        onSuccess?.Invoke(result);
    }

 
    public IEnumerator GetMetrics(Action<MetricsResponse> onSuccess,
                                  Action<string> onError = null)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/metrics");
        req.timeout = TIMEOUT_SECONDS;
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/metrics] {req.error}");
            yield break;
        }

        MetricsResponse result = null;
        try
        {
            result = JsonConvert.DeserializeObject<MetricsResponse>(req.downloadHandler.text);
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/metrics] Parse error: {e.Message}");
            yield break;
        }

        onSuccess?.Invoke(result);
    }
     
 
    public IEnumerator GetPatrolRoutes(
        Action<Dictionary<string, List<string>>> onSuccess,
        Action<string> onError = null)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/patrol-routes");
        req.timeout = TIMEOUT_SECONDS;
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/patrol-routes] {req.error}");
            yield break;
        }

        Dictionary<string, List<string>> result = null;
        try
        {
            result = JsonConvert.DeserializeObject<Dictionary<string, List<string>>>(
                req.downloadHandler.text);
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/patrol-routes] Parse error: {e.Message}");
            yield break;
        }

        onSuccess?.Invoke(result);
    }

 
    public IEnumerator GetCrimeEvents(
        Action<List<CrimeEventData>> onSuccess,
        Action<string> onError = null,
        int limit = 20)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/crime-events?limit={limit}");
        req.timeout = TIMEOUT_SECONDS;
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/crime-events] {req.error}");
            yield break;
        }

        List<CrimeEventData> result = null;
        try
        {
            result = JsonConvert.DeserializeObject<List<CrimeEventData>>(
                req.downloadHandler.text);
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/crime-events] Parse error: {e.Message}");
            yield break;
        }

        onSuccess?.Invoke(result);
    }
 
    public IEnumerator GetHotspots(Action<List<ZoneData>> onSuccess,
                                   Action<string> onError = null)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/hotspots");
        req.timeout = TIMEOUT_SECONDS;
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/hotspots] {req.error}");
            yield break;
        }

        List<ZoneData> result = null;
        try
        {
            result = JsonConvert.DeserializeObject<List<ZoneData>>(
                req.downloadHandler.text);
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/hotspots] Parse error: {e.Message}");
            yield break;
        }

        onSuccess?.Invoke(result);
    }
 
    private IEnumerator PostScenario(object payload,
                                     Action<string> onComplete = null,
                                     Action<string> onError = null)
    {
        string json;
        try
        {
            // Null handling: serialize only non-null, non-zero fields
            json = JsonConvert.SerializeObject(payload, new JsonSerializerSettings
            {
                NullValueHandling = NullValueHandling.Ignore,
                DefaultValueHandling = DefaultValueHandling.Ignore
            });
        }
        catch (Exception e)
        {
            onError?.Invoke($"[/scenario] Serialize error: {e.Message}");
            yield break;
        }

        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);

        using var req = new UnityWebRequest($"{BASE_URL}/scenario", "POST");
        req.uploadHandler = new UploadHandlerRaw(bodyRaw);
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        req.timeout = TIMEOUT_SECONDS;

        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[/scenario] {req.error}");
            yield break;
        }

        onComplete?.Invoke(req.downloadHandler.text);
    }
 

    public void SetPatrolMode(string mode)
    {
        // mode must be: "greedy" | "ai" | "random"
        StartCoroutine(PostScenario(
            new { set_patrol_mode = mode },
            onComplete: r => Debug.Log($"[API] Patrol mode → {mode}"),
            onError: err => Debug.LogWarning($"[API] SetPatrolMode failed: {err}")
        ));
    }

    public void AddPolice(int count)
    {
        StartCoroutine(PostScenario(
            new { add_police = count },
            onComplete: r => Debug.Log($"[API] Added {count} police"),
            onError: err => Debug.LogWarning($"[API] AddPolice failed: {err}")
        ));
    }

    public void RemovePolice(int count)
    {
        StartCoroutine(PostScenario(
            new { remove_police = count },
            onComplete: r => Debug.Log($"[API] Removed {count} police"),
            onError: err => Debug.LogWarning($"[API] RemovePolice failed: {err}")
        ));
    }

    public void SetCivilianCount(int target)
    {
        StartCoroutine(PostScenario(
            new { set_civilian_count = target },
            onComplete: r => Debug.Log($"[API] Civilian count → {target}"),
            onError: err => Debug.LogWarning($"[API] SetCivilianCount failed: {err}")
        ));
    }

    public void SetLightingAll(float level)
    {
        // level: 0.0 (pitch dark) to 1.0 (full brightness)
        StartCoroutine(PostScenario(
            new { set_lighting = new { all = level } },
            onComplete: r => Debug.Log($"[API] Lighting → {level}"),
            onError: err => Debug.LogWarning($"[API] SetLighting failed: {err}")
        ));
    }

    public void SetLightingZone(string zoneId, float level)
    {
        // Set lighting for one specific zone
        var dict = new Dictionary<string, float> { { zoneId, level } };
        StartCoroutine(PostScenario(
            new { set_lighting = dict },
            onComplete: r => Debug.Log($"[API] Lighting zone {zoneId} → {level}"),
            onError: err => Debug.LogWarning($"[API] SetLightingZone failed: {err}")
        ));
    }

    public void JumpToHour(float hour)
    {
        // hour: 0.0 to 24.0
        StartCoroutine(PostScenario(
            new { time_jump = hour },
            onComplete: r => Debug.Log($"[API] Time jump → {hour}h"),
            onError: err => Debug.LogWarning($"[API] JumpToHour failed: {err}")
        ));
    }

    public void ResetMetrics()
    {
        StartCoroutine(PostScenario(
            new { reset_metrics = true },
            onComplete: r => Debug.Log("[API] Metrics reset"),
            onError: err => Debug.LogWarning($"[API] ResetMetrics failed: {err}")
        ));
    }
 
    public IEnumerator TestConnection(Action onSuccess, Action<string> onFail)
    {
        using var req = UnityWebRequest.Get($"{BASE_URL}/state");
        req.timeout = 3;
        yield return req.SendWebRequest();

        if (req.result == UnityWebRequest.Result.Success)
        {
            Debug.Log("[API] Backend connection OK");
            onSuccess?.Invoke();
        }
        else
        {
            string msg = "Cannot reach backend at localhost:8000. " +
                         "Start the Python backend first (python main.py).";
            Debug.LogError($"[API] {msg}");
            onFail?.Invoke(msg);
        }
    }
}