using UnityEngine;
using UnityEngine.Rendering;

public class DayNightController : MonoBehaviour
{
    [Header("Sun Light — assign the Directional Light")]
    public Light sunLight;

    [Header("Intensity Curve")]
    [Tooltip("X = normalized time (0–1 = midnight to midnight), Y = sun intensity")]
    public AnimationCurve sunIntensityCurve = new AnimationCurve(
        new Keyframe(0.00f, 0.0f),   // midnight   — dark
        new Keyframe(0.25f, 0.8f),   // 6 AM       — sunrise
        new Keyframe(0.50f, 1.5f),   // noon       — full brightness
        new Keyframe(0.75f, 0.6f),   // 6 PM       — sunset
        new Keyframe(1.00f, 0.0f)    // midnight   — dark
    );

    [Header("Sun Colors")]
    public Color colorNight = new Color(0.05f, 0.05f, 0.15f);  // deep blue-black
    public Color colorSunrise = new Color(1.00f, 0.50f, 0.20f);  // warm orange
    public Color colorNoon = new Color(1.00f, 0.95f, 0.85f);  // warm white
    public Color colorSunset = new Color(1.00f, 0.40f, 0.15f);  // deep orange
    public Color colorDusk = new Color(0.20f, 0.10f, 0.30f);  // purple dusk

    [Header("Ambient Light Colors")]
    public Color ambientNight = new Color(0.02f, 0.02f, 0.06f);
    public Color ambientDay = new Color(0.25f, 0.28f, 0.35f);

    [Header("Fog Settings")]
    public bool controlFog = true;
    public Color fogColorDay = new Color(0.60f, 0.70f, 0.80f);
    public Color fogColorNight = new Color(0.01f, 0.01f, 0.04f);
    public float fogDensityDay = 0.003f;
    public float fogDensityNight = 0.012f;

    [Header("Smoothing")]
    [Tooltip("How fast lighting transitions. Lower = smoother but slower.")]
    public float transitionSpeed = 1.5f;

    //  Internal 
    private float _currentTimeOfDay = 8f;
    private float _targetTimeOfDay = 8f;
    void Awake()
    {
        // Auto-find the directional light if not assigned
        if (sunLight == null)
            sunLight = GetComponent<Light>();

        if (sunLight == null)
            Debug.LogError("[DayNight] No Light component found. " +
                           "Attach this script to the Directional Light.");

        // Enable fog
        if (controlFog)
            RenderSettings.fog = true;
    }

    void Update()
    {
        // Smoothly interpolate toward the target time
        _currentTimeOfDay = Mathf.Lerp(
            _currentTimeOfDay,
            _targetTimeOfDay,
            Time.deltaTime * transitionSpeed);

        ApplyLighting(_currentTimeOfDay);
    }
    /// <summary>Called every tick by SimulationManager with time_of_day (0–24)</summary>
    public void SetTimeOfDay(float timeOfDay)
    {
        _targetTimeOfDay = timeOfDay;
    }

    private void ApplyLighting(float tod)
    {
        // Normalize time to 0–1 (midnight = 0 = 1)
        float t = tod / 24f;

        // 0h (midnight) = -90° (below horizon)
        // 6h (sunrise)  =   0° (horizon)
        // 12h (noon)    =  90° (directly overhead)
        // 18h (sunset)  = 180° (other horizon)
        float sunAngle = (t * 360f) - 90f;
        transform.rotation = Quaternion.Euler(sunAngle, -30f, 0f);

        if (sunLight != null)
        {
            sunLight.intensity = sunIntensityCurve.Evaluate(t);
            sunLight.color = GetSunColor(tod);

            // Disable shadows at night (performance)
            sunLight.shadows = tod >= 6f && tod <= 20f
                ? LightShadows.Soft
                : LightShadows.None;
        }

        
        float ambientT = Mathf.InverseLerp(5f, 8f, tod)   // dawn ramp up
                       * Mathf.InverseLerp(20f, 17f, tod); // dusk ramp down
        // Clamp to 0-1
        ambientT = Mathf.Clamp01(ambientT);
        RenderSettings.ambientLight = Color.Lerp(ambientNight, ambientDay, ambientT);

        
        if (controlFog)
        {
            float fogT = Mathf.Clamp01(ambientT);
            RenderSettings.fogColor = Color.Lerp(fogColorNight, fogColorDay, fogT);
            RenderSettings.fogDensity = Mathf.Lerp(fogDensityNight, fogDensityDay, fogT);
        }
    }

    
    private Color GetSunColor(float tod)
    {
        // Midnight → sunrise (0–6)
        if (tod < 6f)
            return Color.Lerp(colorNight, colorSunrise, Mathf.InverseLerp(4f, 6f, tod));

        // Sunrise → noon (6–12)
        if (tod < 12f)
            return Color.Lerp(colorSunrise, colorNoon, Mathf.InverseLerp(6f, 12f, tod));

        // Noon → sunset (12–18)
        if (tod < 18f)
            return Color.Lerp(colorNoon, colorSunset, Mathf.InverseLerp(12f, 18f, tod));

        // Sunset → dusk (18–20)
        if (tod < 20f)
            return Color.Lerp(colorSunset, colorDusk, Mathf.InverseLerp(18f, 20f, tod));

        // Dusk → night (20–24)
        return Color.Lerp(colorDusk, colorNight, Mathf.InverseLerp(20f, 24f, tod));
    }
}