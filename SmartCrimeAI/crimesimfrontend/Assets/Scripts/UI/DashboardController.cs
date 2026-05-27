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

    [Header("Metrics Panel")]
    public TextMeshProUGUI totalCrimesText;
    public TextMeshProUGUI totalCaughtText;
    public TextMeshProUGUI catchRateText;
    public TextMeshProUGUI avgResponseText;
    public TextMeshProUGUI patrolEffText;
    public TextMeshProUGUI mlAucText;

    [Header("Crime Log")]
    public Transform logContent;       // Content inside ScrollView
    public GameObject logEntryPrefab;   // TMP text prefab
    private int _maxLogEntries = 12;
    private List<string> _loggedIds = new();

    [Header("Scenario Buttons — assign in Inspector")]
    public Button btnGreedy;
    public Button btnAI;
    public Button btnAddPolice;
    public Button btnRemovePolice;
    public Button btnLightingDay;
    public Button btnLightingNight;

    private SimulationManager _sim;

    void Start()
    {
        _sim = FindFirstObjectByType<SimulationManager>();

        if (_sim == null)
        {
            Debug.LogError("[Dashboard] SimulationManager not found!");
            return;
        }

        // Wire buttons
        btnGreedy?.onClick.AddListener(() => _sim.SetPatrolModeGreedy());
        btnAI?.onClick.AddListener(() => _sim.SetPatrolModeAI());
        btnAddPolice?.onClick.AddListener(() => _sim.AddOnePolice());
        btnRemovePolice?.onClick.AddListener(() => _sim.RemoveOnePolice());
        btnLightingDay?.onClick.AddListener(() => _sim.SetLightingDay());
        btnLightingNight?.onClick.AddListener(() => _sim.SetLightingNight());

        SetupLayout();
    }

    private void SetupLayout()
    {
        //  Top Bar 
        var topBar = simTimeText?.transform.parent;
        if (topBar != null)
        {
            var img = topBar.GetComponent<UnityEngine.UI.Image>();
            if (img) img.color = new Color(0.05f, 0.05f, 0.10f, 0.92f);
        }

        // Style all metric texts
        SetTextStyle(simTimeText, 18, Color.white, FontStyles.Bold);
        SetTextStyle(tickText, 13, new Color(0.6f, 0.6f, 0.7f), FontStyles.Normal);
        SetTextStyle(patrolModeText, 13, new Color(0.4f, 0.7f, 1.0f), FontStyles.Bold);

        //  Metrics Panel 
        SetTextStyle(totalCrimesText, 12, new Color(1.0f, 0.4f, 0.4f), FontStyles.Normal);
        SetTextStyle(totalCaughtText, 12, new Color(0.4f, 1.0f, 0.5f), FontStyles.Normal);
        SetTextStyle(catchRateText, 12, new Color(0.6f, 0.4f, 1.0f), FontStyles.Normal);
        SetTextStyle(avgResponseText, 12, new Color(0.4f, 0.8f, 1.0f), FontStyles.Normal);
        SetTextStyle(patrolEffText, 12, new Color(1.0f, 0.7f, 0.3f), FontStyles.Normal);
        SetTextStyle(mlAucText, 12, new Color(0.7f, 0.7f, 0.7f), FontStyles.Normal);

      
        StyleButton(btnGreedy, "#2255CC", "#4488FF");
        StyleButton(btnAI, "#552299", "#8844FF");
        StyleButton(btnAddPolice, "#1A6632", "#33CC66");
        StyleButton(btnRemovePolice, "#661A1A", "#FF4444");
        StyleButton(btnLightingDay, "#665500", "#FFCC00");
        StyleButton(btnLightingNight, "#0A0A33", "#3333AA");
    }

    private void SetTextStyle(TextMeshProUGUI tmp, int size, Color color, FontStyles style)
    {
        if (tmp == null) return;
        tmp.fontSize = size;
        tmp.color = color;
        tmp.fontStyle = style;
    }

    private void StyleButton(Button btn, string bgHex, string textHex)
    {
        if (btn == null) return;

        // Background
        ColorUtility.TryParseHtmlString(bgHex, out Color bg);
        var img = btn.GetComponent<UnityEngine.UI.Image>();
        if (img) img.color = new Color(bg.r, bg.g, bg.b, 0.85f);

        // Text
        ColorUtility.TryParseHtmlString(textHex, out Color tc);
        var tmp = btn.GetComponentInChildren<TextMeshProUGUI>();
        if (tmp)
        {
            tmp.color = tc;
            tmp.fontSize = 12;
            tmp.fontStyle = FontStyles.Bold;
        }

        // Hover tint
        var colors = btn.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = new Color(1.3f, 1.3f, 1.3f);
        colors.pressedColor = new Color(0.7f, 0.7f, 0.7f);
        btn.colors = colors;
    }

    public void UpdateSimTime(float timeOfDay, int tick)
    {
        // Format time
        int hour = Mathf.FloorToInt(timeOfDay);
        int min = Mathf.FloorToInt((timeOfDay - hour) * 60);
        string ampm = hour >= 12 ? "PM" : "AM";
        int h12 = hour % 12 == 0 ? 12 : hour % 12;

        if (simTimeText)
            simTimeText.text = $"{h12}:{min:D2} {ampm}";

        if (tickText)
            tickText.text = $"Tick {tick}";
    }

    public void UpdateMetrics(MetricsResponse m)
    {
        if (m == null) return;

        if (totalCrimesText) totalCrimesText.text = $"Crimes: {m.total_crimes}";
        if (totalCaughtText) totalCaughtText.text = $"Caught: {m.total_caught}";
        if (catchRateText) catchRateText.text = $"Rate: {m.catch_rate * 100f:F1}%";
        if (avgResponseText) avgResponseText.text = $"Response: {m.avg_response_time:F1}t";
        if (patrolEffText) patrolEffText.text = $"Efficiency: {m.patrol_efficiency * 100f:F1}%";

        // Patrol mode color coding
        if (patrolModeText)
        {
            patrolModeText.text = $"MODE: {m.patrol_mode.ToUpper()}";
            patrolModeText.color = m.patrol_mode switch
            {
                "ai" => new Color(0.6f, 0.3f, 1.0f),
                "greedy" => new Color(0.3f, 0.6f, 1.0f),
                _ => Color.white
            };
        }

        // ML metrics — only show after model trains
        if (mlAucText)
        {
            if (m.ml_metrics != null && m.ml_metrics.roc_auc > 0)
                mlAucText.text = $"ML AUC: {m.ml_metrics.roc_auc:F2}";
            else
                mlAucText.text = "ML: Training...";
        }
    }

    public void AddCrimeLogEntry(CrimeEventData evt)
    {
        if (logContent == null || _loggedIds.Contains(evt.id)) return;
        _loggedIds.Add(evt.id);

        // Trim old entries
        while (logContent.childCount >= _maxLogEntries)
            Destroy(logContent.GetChild(0).gameObject);

        // Create entry
        GameObject entry;
        if (logEntryPrefab != null)
        {
            entry = Instantiate(logEntryPrefab, logContent);
        }
        else
        {
            // Build from scratch if no prefab assigned
            entry = new GameObject("LogEntry");
            entry.transform.SetParent(logContent);
            entry.AddComponent<TextMeshProUGUI>();
        }

        var tmp = entry.GetComponent<TextMeshProUGUI>();
        if (tmp == null) tmp = entry.GetComponentInChildren<TextMeshProUGUI>();
        if (tmp == null) return;

        // Format entry
        int hour = Mathf.FloorToInt(evt.time_of_day);
        int min = Mathf.FloorToInt((evt.time_of_day - hour) * 60);
        string ampm = hour >= 12 ? "PM" : "AM";
        int h12 = hour % 12 == 0 ? 12 : hour % 12;

        string status = evt.caught ? "CAUGHT" : "ESCAPED";
        tmp.text = $"{h12}:{min:D2} {ampm} | {evt.type.ToUpper()} | {evt.zone} | {status}";
        tmp.fontSize = 11;
        tmp.color = evt.caught
            ? new Color(0.3f, 1.0f, 0.5f)   // green
            : new Color(1.0f, 0.3f, 0.3f);  // red

        // Scroll to bottom
        var scrollRect = logContent.GetComponentInParent<ScrollRect>();
        if (scrollRect != null)
            scrollRect.verticalNormalizedPosition = 0f;
    }

    private void StyleButton(Button btn, Color color)
    {
        if (btn == null) return;
        var img = btn.GetComponent<Image>();
        if (img) img.color = new Color(color.r, color.g, color.b, 0.3f);

        var tmp = btn.GetComponentInChildren<TextMeshProUGUI>();
        if (tmp) tmp.color = color;
    }
}