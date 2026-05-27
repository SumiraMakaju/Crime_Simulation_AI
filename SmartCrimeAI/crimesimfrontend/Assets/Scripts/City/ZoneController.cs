// ZoneController.cs
// Attached at runtime by CityBuilder to every spawned zone.
// Receives live data from the API each tick and updates visuals.

using UnityEngine;

public class ZoneController : MonoBehaviour
{
    //  Set by CityBuilder on spawn
    public string ZoneId;
    public string ZoneType;

    //  Child references (auto-found in Awake) 
    private Renderer _heatmapRenderer;
    private Light _streetLight;

    //  Heatmap color targets (lerped in Update for smooth transitions) 
    private Color _targetColor;
    private float _targetLightIntensity;

    // risk_score → color mapping (matches project spec exactly)
    private static readonly Color ColorGreen = new Color(0.10f, 0.80f, 0.20f, 0.25f);
    private static readonly Color ColorYellow = new Color(0.90f, 0.85f, 0.10f, 0.40f);
    private static readonly Color ColorOrange = new Color(0.95f, 0.50f, 0.05f, 0.55f);
    private static readonly Color ColorRed = new Color(0.90f, 0.10f, 0.10f, 0.70f);


    void Awake()
    {
        var ground = transform.Find("Ground");
        if (ground != null)
            _heatmapRenderer = ground.GetComponent<Renderer>();

        _streetLight = GetComponentInChildren<Light>();

        // Set default ground color per zone type
        Color groundColor = ZoneType switch
        {
            "residential" => new Color(0.12f, 0.16f, 0.22f),
            "commercial" => new Color(0.10f, 0.10f, 0.18f),
            "park" => new Color(0.08f, 0.18f, 0.10f),
            "intersection" => new Color(0.10f, 0.10f, 0.10f),
            _ => new Color(0.12f, 0.12f, 0.15f)
        };

        _targetColor = groundColor;

        if (_heatmapRenderer != null)
            _heatmapRenderer.material.color = groundColor;

        _targetLightIntensity = 0.5f;
    }
    // 
    void Update()
    {
        // Smoothly interpolate heatmap color
        if (_heatmapRenderer != null)
        {
            _heatmapRenderer.material.color = Color.Lerp(
                _heatmapRenderer.material.color,
                _targetColor,
                Time.deltaTime * 3f);
        }

        // Smoothly interpolate street light intensity
        if (_streetLight != null)
        {
            _streetLight.intensity = Mathf.Lerp(
                _streetLight.intensity,
                _targetLightIntensity,
                Time.deltaTime * 2f);
        }
    }

    // 
    /// <summary>Called every tick by SimulationManager with fresh /state data</summary>
    public void UpdateFromApi(ZoneData data)
    {
        // Blend base zone color with risk color
        Color baseColor = ZoneType switch
        {
            "residential" => new Color(0.12f, 0.16f, 0.22f),
            "commercial" => new Color(0.10f, 0.10f, 0.18f),
            "park" => new Color(0.08f, 0.18f, 0.10f),
            "intersection" => new Color(0.10f, 0.10f, 0.10f),
            _ => new Color(0.12f, 0.12f, 0.15f)
        };

        Color riskColor = data.risk_score switch
        {
            < 0.3f => baseColor,
            < 0.6f => Color.Lerp(baseColor, new Color(0.4f, 0.3f, 0.0f), 0.4f),
            < 0.8f => Color.Lerp(baseColor, new Color(0.5f, 0.15f, 0.0f), 0.6f),
            _ => Color.Lerp(baseColor, new Color(0.5f, 0.0f, 0.0f), 0.8f)
        };

        _targetColor = riskColor;
        _targetLightIntensity = data.lighting * 0.8f;
    }
}