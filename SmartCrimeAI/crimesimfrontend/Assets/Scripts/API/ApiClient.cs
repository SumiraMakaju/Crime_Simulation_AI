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
                                 string endpoint = "/scenario",
                                 Action<string> onComplete = null,
                                 Action<string> onError = null)
    {
        string json = JsonConvert.SerializeObject(payload, new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore
        });

        Debug.Log($"[API] Sending POST to {endpoint} with payload: {json}");

        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);

        using var req = new UnityWebRequest($"{BASE_URL}{endpoint}", "POST");
        req.uploadHandler = new UploadHandlerRaw(bodyRaw);
        req.downloadHandler = new DownloadHandlerBuffer();
        
        // Explicitly set the request header AND the upload handler content-type to guarantee json delivery
        req.SetRequestHeader("Content-Type", "application/json");
        req.uploadHandler.contentType = "application/json";
        
        req.timeout = TIMEOUT_SECONDS;

        yield return req.SendWebRequest();

        Debug.Log($"[API] POST {endpoint} completed. Status Code: {req.responseCode}, Result: {req.result}, Response Body: {req.downloadHandler?.text}");

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke($"[{endpoint}] {req.error} (Code: {req.responseCode}, Response: {req.downloadHandler?.text})");
            yield break;
        }
        onComplete?.Invoke(req.downloadHandler.text);
    }

    private void RunCoroutine(IEnumerator coroutine)
    {
        if (gameObject.activeInHierarchy && enabled)
        {
            StartCoroutine(coroutine);
        }
        else
        {
            var sim = FindObjectOfType<SimulationManager>();
            if (sim != null)
            {
                Debug.LogWarning("[API] ApiClient GameObject is inactive or disabled! Dynamically routing scenario coroutine through active SimulationManager to guarantee execution.");
                sim.StartCoroutine(coroutine);
            }
            else
            {
                Debug.LogError("[API] CRITICAL: Both ApiClient and SimulationManager are inactive or disabled! Cannot execute network request.");
            }
        }
    }

    public void SetPatrolMode(string mode)
    {
        // mode must be: "greedy" | "ai" | "random"
        var payload = new Dictionary<string, object> { { "set_patrol_mode", mode } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Patrol mode → {mode}"),
            onError: err => Debug.LogWarning($"[API] SetPatrolMode failed: {err}")
        ));
    }

    public void AddPolice(int count)
    {
        var payload = new Dictionary<string, object> { { "add_police", count } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Added {count} police"),
            onError: err => Debug.LogWarning($"[API] AddPolice failed: {err}")
        ));
    }

    public void RemovePolice(int count)
    {
        var payload = new Dictionary<string, object> { { "remove_police", count } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Removed {count} police"),
            onError: err => Debug.LogWarning($"[API] RemovePolice failed: {err}")
        ));
    }

    public void SetCivilianCount(int target)
    {
        var payload = new Dictionary<string, object> { { "set_civilian_count", target } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Civilian count → {target}"),
            onError: err => Debug.LogWarning($"[API] SetCivilianCount failed: {err}")
        ));
    }

    public void SetLightingAll(float level)
    {
        // level: 0.0 (pitch dark) to 1.0 (full brightness)
        var inner = new Dictionary<string, float> { { "all", level } };
        var payload = new Dictionary<string, object> { { "set_lighting", inner } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Lighting → {level}"),
            onError: err => Debug.LogWarning($"[API] SetLighting failed: {err}")
        ));
    }

    public void SetLightingZone(string zoneId, float level)
    {
        // Set lighting for one specific zone
        var dict = new Dictionary<string, float> { { zoneId, level } };
        var payload = new Dictionary<string, object> { { "set_lighting", dict } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Lighting zone {zoneId} → {level}"),
            onError: err => Debug.LogWarning($"[API] SetLightingZone failed: {err}")
        ));
    }

    public void JumpToHour(float hour)
    {
        // hour: 0.0 to 24.0
        var payload = new Dictionary<string, object> { { "time_jump", hour } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log($"[API] Time jump → {hour}h"),
            onError: err => Debug.LogWarning($"[API] JumpToHour failed: {err}")
        ));
    }

    public void ResetMetrics()
    {
        var payload = new Dictionary<string, object> { { "reset_metrics", true } };
        RunCoroutine(PostScenario(
            payload,
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

    public void TriggerBlackout()
    {
        RunCoroutine(PostScenario(
            new Dictionary<string, object>(),
            endpoint: "/scenario/blackout",
            onComplete: r => Debug.Log("[API] Blackout triggered"),
            onError: err => Debug.LogWarning($"[API] Blackout failed: {err}")
        ));
    }

    public void TriggerSaturation()
    {
        RunCoroutine(PostScenario(
            new Dictionary<string, object>(),
            endpoint: "/scenario/saturation",
            onComplete: r => Debug.Log("[API] Saturation triggered"),
            onError: err => Debug.LogWarning($"[API] Saturation failed: {err}")
        ));
    }

    public void TriggerRecovery()
    {
        RunCoroutine(PostScenario(
            new Dictionary<string, object>(),
            endpoint: "/scenario/recovery",
            onComplete: r => Debug.Log("[API] Recovery triggered"),
            onError: err => Debug.LogWarning($"[API] Recovery failed: {err}")
        ));
    }

    public void SetPatrolModeMARL()
    {
        var payload = new Dictionary<string, object> { { "set_patrol_mode", "marl" } };
        RunCoroutine(PostScenario(
            payload,
            onComplete: r => Debug.Log("[API] Patrol mode → MARL"),
            onError: err => Debug.LogWarning($"[API] MARL failed: {err}")
        ));
    }
}