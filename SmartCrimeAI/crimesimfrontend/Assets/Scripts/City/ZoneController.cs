using UnityEngine;

public class ZoneController : MonoBehaviour
{
    public string ZoneId;
    public string ZoneType;

    private Renderer _heatmapRenderer;
    private Light _streetLight;
    private Color _targetColor;
    private float _targetLightIntensity;

    void Awake()
    {
        var ground = transform.Find("Ground");
        if (ground != null)
        {
            _heatmapRenderer = ground.GetComponent<Renderer>();

            if (_heatmapRenderer != null)
            {
                // Create unique material instance per zone
                _heatmapRenderer.material = new Material(_heatmapRenderer.material);

                // Enable emission keyword for night glow
                _heatmapRenderer.material.EnableKeyword("_EMISSION");
                _heatmapRenderer.material.SetColor("_EmissionColor", Color.black);
            }
        }

        _streetLight = GetComponentInChildren<Light>();

        Color defaultColor = ZoneType switch
        {
            "residential" => new Color(0.12f, 0.16f, 0.22f),
            "commercial" => new Color(0.10f, 0.10f, 0.18f),
            "park" => new Color(0.08f, 0.20f, 0.10f),
            "intersection" => new Color(0.10f, 0.10f, 0.10f),
            _ => new Color(0.12f, 0.12f, 0.15f)
        };

        _targetColor = defaultColor;
        _targetLightIntensity = 0.5f;

        ApplyColor(defaultColor);
    }

    void Update()
    {
        if (_heatmapRenderer != null)
        {
            Color current = GetCurrentColor();
            Color lerped = Color.Lerp(current, _targetColor, Time.deltaTime * 3f);
            ApplyColor(lerped);
        }

        if (_streetLight != null)
        {
            _streetLight.intensity = Mathf.Lerp(
                _streetLight.intensity,
                _targetLightIntensity,
                Time.deltaTime * 2f);
        }
    }

    public void UpdateFromApi(ZoneData data)
    {
        Color baseColor = ZoneType switch
        {
            "residential" => new Color(0.12f, 0.16f, 0.22f),
            "commercial" => new Color(0.10f, 0.10f, 0.18f),
            "park" => new Color(0.08f, 0.20f, 0.10f),
            "intersection" => new Color(0.10f, 0.10f, 0.10f),
            _ => new Color(0.12f, 0.12f, 0.15f)
        };

        // Risk color — blended with base
        _targetColor = data.risk_score switch
        {
            < 0.3f => baseColor,
            < 0.6f => Color.Lerp(baseColor, new Color(0.45f, 0.30f, 0.00f), 0.5f),
            < 0.8f => Color.Lerp(baseColor, new Color(0.60f, 0.15f, 0.00f), 0.7f),
            _ => Color.Lerp(baseColor, new Color(0.70f, 0.00f, 0.00f), 0.9f)
        };

        _targetLightIntensity = data.lighting * 0.8f;

        // Emission for night visibility
        if (_heatmapRenderer != null)
        {
            Color emissionColor = data.risk_score switch
            {
                < 0.3f => Color.black,
                < 0.6f => new Color(0.12f, 0.08f, 0.00f),
                < 0.8f => new Color(0.25f, 0.05f, 0.00f),
                _ => new Color(0.40f, 0.00f, 0.00f)
            };

            _heatmapRenderer.material.SetColor("_EmissionColor", emissionColor);
        }
    }

    private void ApplyColor(Color color)
    {
        if (_heatmapRenderer == null) return;

        if (_heatmapRenderer.material.HasProperty("_BaseColor"))
            _heatmapRenderer.material.SetColor("_BaseColor", color);
        else if (_heatmapRenderer.material.HasProperty("_Color"))
            _heatmapRenderer.material.SetColor("_Color", color);
    }

    private Color GetCurrentColor()
    {
        if (_heatmapRenderer == null) return Color.black;

        if (_heatmapRenderer.material.HasProperty("_BaseColor"))
            return _heatmapRenderer.material.GetColor("_BaseColor");
        else if (_heatmapRenderer.material.HasProperty("_Color"))
            return _heatmapRenderer.material.GetColor("_Color");

        return Color.black;
    }
}