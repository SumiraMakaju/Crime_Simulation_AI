using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class CrimeEventSpawner : MonoBehaviour
{
    [Header("Settings")]
    public float markerLifetime = 8f;
    public float riseHeight = 4f;
    public float pulseSpeed = 4f;

    private HashSet<string> _spawnedIds = new();
    private HashSet<string> _caughtIds = new();
    private Dictionary<string, GameObject> _activeAlerts = new();
    private CityBuilder _cityBuilder;

    void Start()
    {
        _cityBuilder = FindObjectOfType<CityBuilder>();

        if (_cityBuilder == null)
            Debug.LogError("[CrimeSpawner] CityBuilder not found in scene!");
        else
            Debug.Log($"[CrimeSpawner] CityBuilder found. IsReady={_cityBuilder.IsReady}. Keys: {_cityBuilder.ZoneConfigs.Count}");
    }

    public void ProcessEvents(List<CrimeEventData> events, int currentTick)
    {
        if (events == null || events.Count == 0) return;

        if (_cityBuilder == null)
        {
            _cityBuilder = FindObjectOfType<CityBuilder>();
            return;
        }

        if (!_cityBuilder.IsReady || _cityBuilder.ZoneConfigs.Count == 0) return;

        foreach (var evt in events)
        {
            // If we already spawned the green caught alert for this crime, ignore it completely to prevent duplicate cycles
            if (_caughtIds.Contains(evt.id)) continue;

            if (_spawnedIds.Contains(evt.id))
            {
                // If a criminal was caught, immediately update their marker from red to green in real-time!
                if (evt.caught && _activeAlerts.TryGetValue(evt.id, out var oldAlert))
                {
                    _caughtIds.Add(evt.id);
                    Destroy(oldAlert);
                    _activeAlerts.Remove(evt.id);
                    StartCoroutine(SpawnAlert(evt, currentTick, 2.4f));
                }
                continue;
            }
            
            _spawnedIds.Add(evt.id);
            if (evt.caught)
            {
                _caughtIds.Add(evt.id);
            }
            StartCoroutine(SpawnAlert(evt, currentTick, evt.caught ? 2.4f : 0f));
        }
    }

    private IEnumerator SpawnAlert(CrimeEventData evt, int currentTick, float delay = 0f)
    {
        if (delay > 0f)
        {
            yield return new WaitForSeconds(delay);
        }

        Debug.Log($"[CrimeSpawner] Spawning alert for zone='{evt.zone}' type='{evt.type}' caught={evt.caught}");
        if (!_cityBuilder.ZoneConfigs.TryGetValue(evt.zone, out var cfg))
        {
            // Try uppercase version just in case
            string upper = evt.zone.ToUpper();
            if (!_cityBuilder.ZoneConfigs.TryGetValue(upper, out cfg))
            {
                Debug.LogWarning($"[CrimeSpawner] Zone '{evt.zone}' not in ZoneConfigs.");
                yield break;
            }
        }

        //  Build the marker from primitives 
        float randX = Random.Range(-1.5f, 1.5f);
        float randZ = Random.Range(-1.5f, 1.5f);
        Vector3 spawnPos = new Vector3(cfg.world_x + 5f + randX, 0f, cfg.world_z + 5f + randZ);

        bool inProgress = !evt.caught && (currentTick - evt.tick < 3);
        Color markerColor = evt.caught
            ? new Color(0.0f, 1.0f, 0.3f)   // green = caught
            : (inProgress ? new Color(1.0f, 0.6f, 0.1f) : new Color(1.0f, 0.15f, 0.15f)); // orange/yellow = in progress, red = escaped

        // Root object
        GameObject root = new GameObject($"Alert_{evt.id}");
        root.transform.position = spawnPos;
        root.transform.SetParent(transform);

        // Spike body
        GameObject spike = GameObject.CreatePrimitive(PrimitiveType.Cube);
        spike.name = "Spike";
        spike.transform.SetParent(root.transform);
        spike.transform.localPosition = new Vector3(0, 1.5f, 0);
        spike.transform.localScale = new Vector3(0.25f, 3f, 0.25f);
        Destroy(spike.GetComponent<Collider>());
        SetMaterialColor(spike, markerColor);

        // Diamond top
        GameObject diamond = GameObject.CreatePrimitive(PrimitiveType.Cube);
        diamond.name = "Diamond";
        diamond.transform.SetParent(root.transform);
        diamond.transform.localPosition = new Vector3(0, 3.2f, 0);
        diamond.transform.localScale = new Vector3(0.55f, 0.55f, 0.55f);
        diamond.transform.localEulerAngles = new Vector3(45f, 45f, 0f);
        Destroy(diamond.GetComponent<Collider>());
        SetMaterialColor(diamond, markerColor);

        // Glow light
        GameObject lightGo = new GameObject("GlowLight");
        lightGo.transform.SetParent(root.transform);
        lightGo.transform.localPosition = new Vector3(0, 2f, 0);
        Light glow = lightGo.AddComponent<Light>();
        glow.type = LightType.Point;
        glow.color = markerColor;
        glow.intensity = 4f;
        glow.range = 10f;

        // World-space TMP label
        GameObject labelGo = new GameObject("Label");
        labelGo.transform.SetParent(root.transform);
        labelGo.transform.localPosition = new Vector3(0, 4.5f, 0);
        labelGo.transform.localScale = new Vector3(0.08f, 0.08f, 0.08f);
        TextMeshPro tmp = labelGo.AddComponent<TextMeshPro>();

        // Copy font from the main dashboard to prevent blank boxes
        var dashboard = FindObjectOfType<DashboardController>();
        if (dashboard != null && dashboard.simTimeText != null)
        {
            tmp.font = dashboard.simTimeText.font;
        }

        tmp.text = BuildAlertText(evt, currentTick);
        tmp.color = markerColor;
        tmp.fontSize = 28;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.fontStyle = FontStyles.Bold;

        // Always face camera
        labelGo.AddComponent<FaceCamera>();

        // Cache the alert and animate
        _activeAlerts[evt.id] = root;
        yield return StartCoroutine(AnimateMarker(root, glow, tmp, markerColor, evt.id));
    }

    private IEnumerator AnimateMarker(
        GameObject root, Light glow, TextMeshPro tmp, Color baseColor, string id)
    {
        // Phase 1: Rise up from ground (0.4s)
        float riseTime = 0.4f;
        float elapsed = 0f;
        
        if (root == null) yield break;
        Vector3 startPos = root.transform.position;
        Vector3 endPos = startPos + Vector3.up * riseHeight;
        root.transform.localScale = Vector3.zero;

        while (elapsed < riseTime)
        {
            if (root == null) yield break;
            elapsed += Time.deltaTime;
            float t = elapsed / riseTime;
            float ease = 1f - Mathf.Pow(1f - t, 3f);  // ease out cubic

            root.transform.position = Vector3.Lerp(startPos, endPos, ease);
            root.transform.localScale = Vector3.Lerp(Vector3.zero, Vector3.one, ease);
            yield return null;
        }

        if (root == null) yield break;
        root.transform.position = endPos;
        root.transform.localScale = Vector3.one;

        // Phase 2: Pulse for lifetime
        float aliveTime = 0f;
        while (aliveTime < markerLifetime)
        {
            if (root == null) yield break;
            aliveTime += Time.deltaTime;

            // Pulse scale
            float pulse = 1f + Mathf.Sin(Time.time * pulseSpeed) * 0.12f;
            root.transform.localScale = Vector3.one * pulse;

            // Pulse light
            if (glow != null)
                glow.intensity = 3f + Mathf.Sin(Time.time * pulseSpeed * 1.5f) * 1.5f;

            // Spin diamond
            var diamond = root.transform.Find("Diamond");
            if (diamond != null)
                diamond.Rotate(0, 90f * Time.deltaTime, 0, Space.World);

            yield return null;
        }

        // Phase 3: Fade out (1.5s)
        float fadeTime = 1.5f;
        float fadeElapsed = 0f;

        if (root == null) yield break;
        var renderers = root.GetComponentsInChildren<Renderer>();

        while (fadeElapsed < fadeTime)
        {
            if (root == null) yield break;
            fadeElapsed += Time.deltaTime;
            float alpha = Mathf.Lerp(1f, 0f, fadeElapsed / fadeTime);

            foreach (var r in renderers)
            {
                if (r == null) continue;
                if (r.material.shader.name.Contains("TextMeshPro")) continue;
                if (!r.material.HasProperty("_BaseColor") && !r.material.HasProperty("_Color")) continue;
                Color c = r.material.color;
                r.material.color = new Color(c.r, c.g, c.b, alpha);
            }

            if (glow != null) glow.intensity = Mathf.Lerp(4f, 0f, fadeElapsed / fadeTime);
            if (tmp != null) tmp.alpha = alpha;

            yield return null;
        }

        if (root != null) Destroy(root);
        _activeAlerts.Remove(id);
    }

    private string BuildAlertText(CrimeEventData evt, int currentTick)
    {
        string icon = evt.caught ? "[CAUGHT]" : "[CRIME]";

        string crimeType = evt.type switch
        {
            "theft" => "THEFT",
            "assault" => "ASSAULT",
            "vandalism" => "VANDALISM",
            "burglary" => "BURGLARY",
            _ => evt.type.ToUpper()
        };

        bool inProgress = !evt.caught && (currentTick - evt.tick < 3);
        string status = evt.caught ? "CRIMINAL CAUGHT" : (inProgress ? "CRIME IN PROGRESS" : "CRIMINAL ESCAPED");

        int hour = Mathf.FloorToInt(evt.time_of_day);
        int min = Mathf.FloorToInt((evt.time_of_day - hour) * 60);
        string ampm = hour >= 12 ? "PM" : "AM";
        int h12 = hour % 12 == 0 ? 12 : hour % 12;

        return $"{icon} {crimeType}\nZone {evt.zone} - {h12}:{min:D2} {ampm}\n{status}";
    }

    private void SetMaterialColor(GameObject go, Color color)
    {
        var r = go.GetComponent<Renderer>();
        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetFloat("_Surface", 1);    // transparent
        mat.SetFloat("_Blend", 0);    // alpha blend
        mat.color = color;
        r.material = mat;
    }

    public void ClearHistory()
    {
        _spawnedIds.Clear();
        _caughtIds.Clear();
        _activeAlerts.Clear();
    }
}