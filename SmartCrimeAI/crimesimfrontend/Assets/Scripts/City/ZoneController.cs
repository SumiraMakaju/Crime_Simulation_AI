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
    // Color the ground instead of a separate plane
    var ground = transform.Find("Ground");
    if (ground != null)
        _heatmapRenderer = ground.GetComponent<Renderer>();

    _streetLight = GetComponentInChildren<Light>();
    _targetColor = new Color(0.12f, 0.16f, 0.22f); // default dark ground
    _targetLightIntensity = 1.5f;
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
        // Map risk_score to heatmap color
        _targetColor = data.risk_score switch
        {
            < 0.3f => ColorGreen,
            < 0.6f => ColorYellow,
            < 0.8f => ColorOrange,
            _ => ColorRed
        };

        // Drive street light from lighting value (0.0–1.0 → 0.0–3.0 Unity intensity)
        _targetLightIntensity = data.lighting * 3f;
    }
}