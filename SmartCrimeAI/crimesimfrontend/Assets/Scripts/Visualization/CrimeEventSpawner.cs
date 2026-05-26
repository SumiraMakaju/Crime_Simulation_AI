using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class CrimeEventSpawner : MonoBehaviour
{
    [Header("Marker Prefabs")]
    public GameObject crimeMarkerPrefab;      // red spike
    public GameObject interceptMarkerPrefab;  // green spike

    [Header("Settings")]
    public float markerLifetime = 10f;   // seconds before fade starts
    public float fadeDuration = 3f;    // seconds to fade out
    public float pulseSpeed = 3f;    // how fast marker pulses
    public float pulseScaleAmount = 0.15f; // how much it scales up/down
     
    private HashSet<string> _spawnedIds = new();
    private CityBuilder _cityBuilder;

 
    void Awake()
    {
        _cityBuilder = FindObjectOfType<CityBuilder>();
    }


    public void ProcessEvents(List<CrimeEventData> events)
    {
        if (events == null) return;

        // Wait until CityBuilder has finished loading zones
        if (_cityBuilder == null || !_cityBuilder.IsReady) return;

        foreach (var evt in events)
        {
            if (_spawnedIds.Contains(evt.id)) continue;
            _spawnedIds.Add(evt.id);
            SpawnMarker(evt);
        }
    }

    private void SpawnMarker(CrimeEventData evt)
    {
        if (_cityBuilder == null) return;

        // Look up zone world position
        if (!_cityBuilder.ZoneConfigs.TryGetValue(evt.zone, out var cfg))
        {
            Debug.LogWarning($"[CrimeSpawner] Zone {evt.zone} not found in config.");
            return;
        }

        // Pick prefab based on whether criminal was caught
        GameObject prefab = evt.caught ? interceptMarkerPrefab : crimeMarkerPrefab;

        if (prefab == null)
        {
            Debug.LogWarning("[CrimeSpawner] Marker prefab not assigned!");
            return;
        }

        // Spawn at zone center, slightly randomized so overlapping events
        // are still visible
        float randX = Random.Range(-2f, 2f);
        float randZ = Random.Range(-2f, 2f);
        Vector3 spawnPos = new Vector3(
            cfg.world_x + 5f + randX,
            0f,
            cfg.world_z + 5f + randZ);

        GameObject marker = Instantiate(prefab, spawnPos, Quaternion.identity, transform);
        marker.name = $"Crime_{evt.id}";

        // Set label text
        var label = marker.GetComponentInChildren<TextMeshPro>();
        if (label != null)
        {
            label.text = FormatCrimeLabel(evt);
            label.color = evt.caught ? Color.green : Color.red;
        }

        // Start pulse + lifetime coroutines
        StartCoroutine(PulseMarker(marker));
        StartCoroutine(LifetimeAndFade(marker, markerLifetime, fadeDuration));
    }

    
    private IEnumerator PulseMarker(GameObject marker)
    {
        if (marker == null) yield break;

        Vector3 baseScale = marker.transform.localScale;

        while (marker != null)
        {
            float pulse = 1f + Mathf.Sin(Time.time * pulseSpeed) * pulseScaleAmount;
            marker.transform.localScale = baseScale * pulse;
            yield return null;
        }
    }
 
    private IEnumerator LifetimeAndFade(GameObject marker, float lifetime, float fadeTime)
    {
        // Wait full lifetime
        yield return new WaitForSeconds(lifetime);

        if (marker == null) yield break;

        // Collect all renderers and lights for fading
        var renderers = marker.GetComponentsInChildren<Renderer>();
        var lights = marker.GetComponentsInChildren<Light>();
        var labels = marker.GetComponentsInChildren<TextMeshPro>();

        float elapsed = 0f;

        // Store original values
        var originalColors = new Color[renderers.Length];
        var originalIntensities = new float[lights.Length];
        var originalLabelColors = new Color[labels.Length];

        for (int i = 0; i < renderers.Length; i++)
            originalColors[i] = renderers[i].material.color;

        for (int i = 0; i < lights.Length; i++)
            originalIntensities[i] = lights[i].intensity;

        for (int i = 0; i < labels.Length; i++)
            originalLabelColors[i] = labels[i].color;

        // Fade out
        while (elapsed < fadeTime && marker != null)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / fadeTime;  // 0 → 1

            // Fade renderers
            for (int i = 0; i < renderers.Length; i++)
            {
                if (renderers[i] == null) continue;
                Color c = originalColors[i];
                renderers[i].material.color = new Color(c.r, c.g, c.b, Mathf.Lerp(c.a, 0f, t));
            }

            // Fade lights
            for (int i = 0; i < lights.Length; i++)
            {
                if (lights[i] == null) continue;
                lights[i].intensity = Mathf.Lerp(originalIntensities[i], 0f, t);
            }

            // Fade labels
            for (int i = 0; i < labels.Length; i++)
            {
                if (labels[i] == null) continue;
                Color c = originalLabelColors[i];
                labels[i].color = new Color(c.r, c.g, c.b, Mathf.Lerp(c.a, 0f, t));
            }

            yield return null;
        }

        // Destroy after fade
        if (marker != null)
            Destroy(marker);
    }
 
    private string FormatCrimeLabel(CrimeEventData evt)
    {
        string type = evt.type switch
        {
            "theft" => "THEFT",
            "assault" => "ASSAULT",
            "vandalism" => "VANDAL",
            "burglary" => "BURGLAR",
            _ => evt.type.ToUpper()
        };

        return evt.caught ? $"✓ {type}" : type;
    }
 
    public void ClearHistory()
    {
        _spawnedIds.Clear();
    }
}