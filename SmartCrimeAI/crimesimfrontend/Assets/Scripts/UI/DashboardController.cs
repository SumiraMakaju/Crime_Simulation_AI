using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class DashboardController : MonoBehaviour
{
    [Header("Top Bar")]
    public TextMeshProUGUI simTimeText;
    public TextMeshProUGUI tickText;
    public TextMeshProUGUI patrolModeText;
    public TextMeshProUGUI activeScenarioText;

    [Header("Metrics")]
    public TextMeshProUGUI totalCrimesText;
    public TextMeshProUGUI totalCaughtText;
    public TextMeshProUGUI catchRateText;
    public TextMeshProUGUI avgResponseText;
    public TextMeshProUGUI patrolEffText;
    public TextMeshProUGUI mlAucText;

    [Header("Crime Log")]
    public Transform logContent;
    private int _maxLogEntries = 10;
    private List<string> _loggedIds = new();

    [Header("Patrol Mode Buttons")]
    public Button btnGreedy;
    public Button btnAI;
    public Button btnMARLPatrol;

    [Header("Police Buttons")]
    public Button btnAddPolice;
    public Button btnRemovePolice;

    [Header("Lighting Buttons")]
    public Button btnLightingDay;
    public Button btnLightingNight;

    [Header("Macro Scenario Buttons")]
    public Button btnBlackout;
    public Button btnSaturation;
    public Button btnRecovery;

    [Header("Other Buttons")]
    public Button btnResetMetrics;

    private SimulationManager _sim;

    void Start()
    {
        _sim = FindFirstObjectByType<SimulationManager>();

        if (_sim == null)
        {
            Debug.LogError("[Dashboard] SimulationManager not found!");
            return;
        }

        WireButtons();
        StyleAllText();
        Debug.Log("[Dashboard] Ready.");
    }

    private void WireButtons()
    {
        // Clear all listeners first
        btnGreedy?.onClick.RemoveAllListeners();
        btnAI?.onClick.RemoveAllListeners();
        btnMARLPatrol?.onClick.RemoveAllListeners();
        btnAddPolice?.onClick.RemoveAllListeners();
        btnRemovePolice?.onClick.RemoveAllListeners();
        btnLightingDay?.onClick.RemoveAllListeners();
        btnLightingNight?.onClick.RemoveAllListeners();
        btnBlackout?.onClick.RemoveAllListeners();
        btnSaturation?.onClick.RemoveAllListeners();
        btnRecovery?.onClick.RemoveAllListeners();
        btnResetMetrics?.onClick.RemoveAllListeners();

        // Wire fresh
        btnGreedy?.onClick.AddListener(() => _sim.SetPatrolModeGreedy());
        btnAI?.onClick.AddListener(() => _sim.SetPatrolModeAI());
        btnMARLPatrol?.onClick.AddListener(() => _sim.SetPatrolModeMARL());
        btnAddPolice?.onClick.AddListener(() => _sim.AddOnePolice());
        btnRemovePolice?.onClick.AddListener(() => _sim.RemoveOnePolice());
        btnLightingDay?.onClick.AddListener(() => _sim.SetLightingDay());
        btnLightingNight?.onClick.AddListener(() => _sim.SetLightingNight());
        btnBlackout?.onClick.AddListener(() => _sim.TriggerBlackout());
        btnSaturation?.onClick.AddListener(() => _sim.TriggerSaturation());
        btnRecovery?.onClick.AddListener(() => _sim.TriggerRecovery());
        btnResetMetrics?.onClick.AddListener(() => _sim.ResetMetrics());

        Debug.Log("[Dashboard] Buttons wired.");

        // Style buttons
        StyleButton(btnGreedy, new Color(0.10f, 0.25f, 0.70f), "#4488FF", "GREEDY");
        StyleButton(btnAI, new Color(0.30f, 0.10f, 0.60f), "#AA44FF", "AI PATROL");
        StyleButton(btnMARLPatrol, new Color(0.50f, 0.10f, 0.40f), "#FF44CC", "MARL");
        StyleButton(btnAddPolice, new Color(0.05f, 0.35f, 0.15f), "#00FF64", "+ POLICE");
        StyleButton(btnRemovePolice, new Color(0.45f, 0.05f, 0.05f), "#FF4444", "- POLICE");
        StyleButton(btnLightingDay, new Color(0.45f, 0.32f, 0.00f), "#FFCC00", "DAY");
        StyleButton(btnLightingNight, new Color(0.05f, 0.05f, 0.25f), "#4466FF", "NIGHT");
        StyleButton(btnBlackout, new Color(0.40f, 0.02f, 0.02f), "#FF2222", "BLACKOUT");
        StyleButton(btnSaturation, new Color(0.02f, 0.08f, 0.40f), "#2255FF", "SATURATION");
        StyleButton(btnRecovery, new Color(0.02f, 0.35f, 0.10f), "#00FF88", "RECOVERY");
        StyleButton(btnResetMetrics, new Color(0.20f, 0.20f, 0.20f), "#AAAAAA", "RESET");
    }

    private void StyleButton(Button btn, Color bgColor, string hexText, string label)
    {
        if (btn == null) return;

        var img = btn.GetComponent<Image>();
        if (img) img.color = new Color(bgColor.r, bgColor.g, bgColor.b, 0.85f);

        var tmp = btn.GetComponentInChildren<TextMeshProUGUI>();
        if (tmp)
        {
            tmp.text = label;
            tmp.fontSize = 10;
            tmp.fontStyle = FontStyles.Bold;
            ColorUtility.TryParseHtmlString(hexText, out Color tc);
            tmp.color = tc;
        }

        var colors = btn.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = new Color(1.3f, 1.3f, 1.3f);
        colors.pressedColor = new Color(0.6f, 0.6f, 0.6f);
        btn.colors = colors;
    }

    private void StyleAllText()
    {
        SetStyle(simTimeText, 22, "#FFFFFF", true);
        SetStyle(tickText, 12, "#AACCDD", false);
        SetStyle(patrolModeText, 12, "#44AAFF", true);
        SetStyle(activeScenarioText, 12, "#44FF88", true);
        SetStyle(totalCrimesText, 14, "#FF4444", true);
        SetStyle(totalCaughtText, 14, "#00FF64", true);
        SetStyle(catchRateText, 14, "#AA44FF", true);
        SetStyle(avgResponseText, 14, "#00D4FF", true);
        SetStyle(patrolEffText, 14, "#FFAA00", true);
        SetStyle(mlAucText, 14, "#FF88CC", true);
    }

    private void SetStyle(TextMeshProUGUI tmp, int size, string hex, bool bold)
    {
        if (tmp == null) return;
        tmp.fontSize = size;
        tmp.fontStyle = bold ? FontStyles.Bold : FontStyles.Normal;
        ColorUtility.TryParseHtmlString(hex, out Color c);
        tmp.color = c;
    }

    public void UpdateSimTime(float timeOfDay, int tick)
    {
        int hour = Mathf.FloorToInt(timeOfDay);
        int min = Mathf.FloorToInt((timeOfDay - hour) * 60);
        string ampm = hour >= 12 ? "PM" : "AM";
        int h12 = hour % 12 == 0 ? 12 : hour % 12;

        if (simTimeText) simTimeText.text = $"{h12}:{min:D2} {ampm}";
        if (tickText) tickText.text = $"Tick {tick:000000}";
    }

    public void UpdateMetrics(MetricsResponse m)
    {
        if (m == null) return;

        if (totalCrimesText) totalCrimesText.text = m.total_crimes.ToString();
        if (totalCaughtText) totalCaughtText.text = m.total_caught.ToString();
        if (catchRateText) catchRateText.text = $"{m.catch_rate * 100f:F1}%";
        if (avgResponseText) avgResponseText.text = $"{m.avg_response_time:F1}t";
        if (patrolEffText) patrolEffText.text = $"{m.patrol_efficiency * 100f:F1}%";

        if (patrolModeText)
        {
            patrolModeText.text = $"MODE: {m.patrol_mode?.ToUpper()}";
            string hex = m.patrol_mode switch
            {
                "ai" => "#AA44FF",
                "marl" => "#FF44CC",
                _ => "#44AAFF"
            };
            ColorUtility.TryParseHtmlString(hex, out Color mc);
            patrolModeText.color = mc;
        }

        if (mlAucText)
        {
            mlAucText.text = m.ml_metrics != null && m.ml_metrics.roc_auc > 0
                ? $"AUC {m.ml_metrics.roc_auc:F2}"
                : "ML: Training...";
        }
    }

    public void UpdateScenario(string scenario)
    {
        if (activeScenarioText == null) return;

        switch (scenario)
        {
            case "blackout":
                activeScenarioText.text = "BLACKOUT ACTIVE";
                activeScenarioText.color = new Color(1f, 0.2f, 0.2f);
                break;
            case "saturation":
                activeScenarioText.text = "EMERGENCY DISPATCH";
                activeScenarioText.color = new Color(1f, 0.6f, 0.1f);
                break;
            default:
                activeScenarioText.text = "NORMAL OPERATIONS";
                activeScenarioText.color = new Color(0.2f, 1f, 0.5f);
                break;
        }
    }

    public void AddCrimeLogEntry(CrimeEventData evt)
    {
        if (logContent == null || _loggedIds.Contains(evt.id)) return;
        _loggedIds.Add(evt.id);

        while (logContent.childCount >= _maxLogEntries)
        {
            var oldest = logContent.GetChild(0).gameObject;
            oldest.transform.SetParent(null);
            Destroy(oldest);
        }

        var entry = new GameObject("LogEntry_" + evt.id);
        entry.transform.SetParent(logContent, false);

        var le = entry.AddComponent<LayoutElement>();
        le.preferredHeight = 20;
        le.flexibleWidth = 1;

        var tmp = entry.AddComponent<TextMeshProUGUI>();
        int hour = Mathf.FloorToInt(evt.time_of_day);
        int min = Mathf.FloorToInt((evt.time_of_day - hour) * 60);
        string ampm = hour >= 12 ? "PM" : "AM";
        int h12 = hour % 12 == 0 ? 12 : hour % 12;
        string status = evt.caught ? "CAUGHT" : "ESCAPED";

        tmp.text = $"{h12}:{min:D2}{ampm} {evt.type.ToUpper()} {evt.zone} {status}";
        tmp.fontSize = 10;
        tmp.fontStyle = FontStyles.Bold;
        tmp.color = evt.caught
            ? new Color(0.2f, 1.0f, 0.4f)
            : new Color(1.0f, 0.3f, 0.3f);

        var sr = logContent.GetComponentInParent<ScrollRect>();
        if (sr != null)
        {
            Canvas.ForceUpdateCanvases();
            sr.verticalNormalizedPosition = 0f;
        }
    }
}