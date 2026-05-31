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

    [Header("Patrol Mode Buttons")]
    public Button btnGreedy;
    public Button btnAI;
    public Button btnMARLPatrol;

    [Header("Police Buttons")]
    public Button btnAddPolice;
    public Button btnRemovePolice;



    [Header("Macro Scenario Buttons")]
    public Button btnBlackout;
    public Button btnSaturation;
    public Button btnRecovery;

    [Header("Other Buttons")]
    public Button btnResetMetrics;

    private SimulationManager _sim;

    void Start()
    {
        Debug.Log("[DashboardController] Start initiated.");
        
        // Dynamic search to locate the active, working SimulationManager (bypassing duplicate dummy instances!)
        var sims = FindObjectsOfType<SimulationManager>();
        foreach (var s in sims)
        {
            if (s.apiClient != null)
            {
                _sim = s;
                // Auto-heal the other side as well by bi-directionally assigning us!
                s.dashboardController = this;
                Debug.Log($"[DashboardController] Bi-directionally resolved and auto-wired active SimulationManager: '{s.gameObject.name}' with ApiClient '{s.apiClient.gameObject.name}'");
                break;
            }
        }

        if (_sim == null)
        {
            _sim = FindObjectOfType<SimulationManager>();
            if (_sim != null)
            {
                Debug.LogWarning($"[DashboardController] Active SimulationManager with assigned ApiClient not found! Falling back to default instance: {_sim.gameObject.name}");
            }
        }

        if (_sim == null)
        {
            Debug.LogError("[DashboardController] SimulationManager NOT found in scene!");
            return;
        }

        // Verify or dynamically create EventSystem to make sure clicks work!
        var eventSystem = FindObjectOfType<UnityEngine.EventSystems.EventSystem>();
        if (eventSystem == null)
        {
            Debug.LogWarning("[DashboardController] EventSystem NOT found in scene! Dynamically creating a new EventSystem to restore UI click functionality.");
            GameObject eventSystemGo = new GameObject("EventSystem");
            eventSystem = eventSystemGo.AddComponent<UnityEngine.EventSystems.EventSystem>();
            eventSystemGo.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
            Debug.Log("[DashboardController] Dynamically created and configured EventSystem + StandaloneInputModule successfully.");
        }
        else
        {
            Debug.Log($"[DashboardController] EventSystem verified active: {eventSystem.name}");
        }



        // Robust dynamic resolution of key UI text fields if left unassigned
        ResolveText(ref simTimeText, "SimTimeText", "TimeText");
        ResolveText(ref tickText, "TickText");
        ResolveText(ref patrolModeText, "PatrolModeText", "ModeText");
        ResolveText(ref activeScenarioText, "ActiveScenarioText", "ScenarioText");
        ResolveText(ref totalCrimesText, "TotalCrimesText");
        ResolveText(ref totalCaughtText, "TotalCaughtText");
        ResolveText(ref catchRateText, "CatchRateText");
        ResolveText(ref avgResponseText, "AvgResponseText");
        ResolveText(ref patrolEffText, "PatrolEffText");
        ResolveText(ref mlAucText, "MlAucText");

        // Robust fallback button assignments if left null in the Inspector
        ResolveButton(ref btnGreedy, "BtnGreedy");
        ResolveButton(ref btnAI, "BtnAI");
        ResolveButton(ref btnMARLPatrol, "BtnMARL", "BtnMARLPatrol");
        ResolveButton(ref btnAddPolice, "BtnAddPolice");
        ResolveButton(ref btnRemovePolice, "BtnRemovePolice");

        ResolveButton(ref btnBlackout, "BtnBlackout");
        ResolveButton(ref btnSaturation, "BtnSaturation");
        ResolveButton(ref btnRecovery, "BtnRecovery");
        ResolveButton(ref btnResetMetrics, "BtnResetMetrics");

        WireButtons();
        Debug.Log("[DashboardController] Initialization complete. Ready.");
    }

    private void ResolveButton(ref Button btn, string name, string fallbackName = "")
    {
        if (btn != null)
        {
            Debug.Log($"[DashboardController] Button '{name}' already assigned via Inspector.");
            // Verify parent canvas has a GraphicRaycaster component
            var canvas = btn.GetComponentInParent<Canvas>();
            if (canvas != null && canvas.GetComponent<GraphicRaycaster>() == null)
            {
                Debug.LogWarning($"[DashboardController] Canvas '{canvas.name}' containing button '{name}' is missing a GraphicRaycaster! Adding one dynamically.");
                canvas.gameObject.AddComponent<GraphicRaycaster>();
            }
            return;
        }

        var go = GameObject.Find(name);
        if (go == null && !string.IsNullOrEmpty(fallbackName))
        {
            go = GameObject.Find(fallbackName);
        }

        if (go != null)
        {
            btn = go.GetComponent<Button>();
            Debug.Log($"[DashboardController] Resolved null button '{name}' from scene hierarchy: {go.name}");
            
            // Verify parent canvas has a GraphicRaycaster component
            var canvas = btn.GetComponentInParent<Canvas>();
            if (canvas != null && canvas.GetComponent<GraphicRaycaster>() == null)
            {
                Debug.LogWarning($"[DashboardController] Canvas '{canvas.name}' containing button '{name}' is missing a GraphicRaycaster! Adding one dynamically.");
                canvas.gameObject.AddComponent<GraphicRaycaster>();
            }
        }
        else
        {
            Debug.LogWarning($"[DashboardController] Button '{name}' is null and could NOT be found in scene hierarchy!");
        }
    }

    private void ResolveText(ref TextMeshProUGUI text, string name, string fallbackName = "")
    {
        if (text != null)
        {
            Debug.Log($"[DashboardController] Text element '{name}' already assigned via Inspector.");
            return;
        }

        var go = GameObject.Find(name);
        if (go == null && !string.IsNullOrEmpty(fallbackName))
        {
            go = GameObject.Find(fallbackName);
        }

        if (go != null)
        {
            text = go.GetComponent<TextMeshProUGUI>();
            Debug.Log($"[DashboardController] Resolved null text element '{name}' from scene hierarchy: {go.name}");
        }
        else
        {
            Debug.LogWarning($"[DashboardController] Text element '{name}' is null and could NOT be found in scene hierarchy!");
        }
    }

    public void UpdatePatrolModeUI(string mode)
    {
        if (patrolModeText == null) return;
        patrolModeText.text = $"MODE: {mode.ToUpper()}";
        string hex = mode switch
        {
            "ai" => "#AA44FF",
            "marl" => "#FF44CC",
            "random" => "#FFAA00",
            _ => "#44AAFF"
        };
        ColorUtility.TryParseHtmlString(hex, out Color mc);
        patrolModeText.color = mc;
    }

    private void WireButtons()
    {
        Debug.Log("[DashboardController] Wiring button listeners...");
        // Clear all listeners first
        btnGreedy?.onClick.RemoveAllListeners();
        btnAI?.onClick.RemoveAllListeners();
        btnMARLPatrol?.onClick.RemoveAllListeners();
        btnAddPolice?.onClick.RemoveAllListeners();
        btnRemovePolice?.onClick.RemoveAllListeners();
        btnBlackout?.onClick.RemoveAllListeners();
        btnSaturation?.onClick.RemoveAllListeners();
        btnRecovery?.onClick.RemoveAllListeners();
        btnResetMetrics?.onClick.RemoveAllListeners();

        // Wire fresh with instant, optimistic UI feedback
        if (btnGreedy != null) btnGreedy.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnGreedy clicked. Sending Greedy Patrol mode.");
            _sim.SetPatrolModeGreedy();
            UpdatePatrolModeUI("greedy");
        });
        if (btnAI != null) btnAI.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnAI clicked. Sending AI Patrol mode.");
            _sim.SetPatrolModeAI();
            UpdatePatrolModeUI("ai");
        });
        if (btnMARLPatrol != null) btnMARLPatrol.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnMARLPatrol clicked. Sending MARL Patrol mode.");
            _sim.SetPatrolModeMARL();
            UpdatePatrolModeUI("marl");
        });
        if (btnAddPolice != null) btnAddPolice.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnAddPolice clicked. Adding police officer.");
            _sim.AddOnePolice();
        });
        if (btnRemovePolice != null) btnRemovePolice.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnRemovePolice clicked. Removing police officer.");
            _sim.RemoveOnePolice();
        });
        if (btnBlackout != null) btnBlackout.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnBlackout clicked. Triggering blackout macro.");
            _sim.TriggerBlackout();
            UpdateScenario("blackout");
            UpdatePatrolModeUI("greedy");
        });
        if (btnSaturation != null) btnSaturation.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnSaturation clicked. Triggering saturation macro.");
            _sim.TriggerSaturation();
            UpdateScenario("saturation");
            UpdatePatrolModeUI("marl");
        });
        if (btnRecovery != null) btnRecovery.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnRecovery clicked. Triggering recovery macro.");
            _sim.TriggerRecovery();
            UpdateScenario("normal");
        });
        if (btnResetMetrics != null) btnResetMetrics.onClick.AddListener(() => {
            Debug.Log("[DashboardController] BtnResetMetrics clicked. Resetting dashboard metrics.");
            _sim.ResetMetrics();
        });

        Debug.Log("[DashboardController] All button listeners wired successfully.");

        // Style buttons
        /*
        StyleButton(btnGreedy, new Color(0.10f, 0.25f, 0.70f), "#4488FF", "GREEDY");
        StyleButton(btnAI, new Color(0.30f, 0.10f, 0.60f), "#AA44FF", "AI PATROL");
        StyleButton(btnMARLPatrol, new Color(0.50f, 0.10f, 0.40f), "#FF44CC", "MARL");
        StyleButton(btnAddPolice, new Color(0.05f, 0.35f, 0.15f), "#00FF64", "+ POLICE");
        StyleButton(btnRemovePolice, new Color(0.45f, 0.05f, 0.05f), "#FF4444", "- POLICE");
        StyleButton(btnBlackout, new Color(0.40f, 0.02f, 0.02f), "#FF2222", "BLACKOUT");
        StyleButton(btnSaturation, new Color(0.02f, 0.08f, 0.40f), "#2255FF", "SATURATION");
        StyleButton(btnRecovery, new Color(0.02f, 0.35f, 0.10f), "#00FF88", "RECOVERY");
        StyleButton(btnResetMetrics, new Color(0.20f, 0.20f, 0.20f), "#AAAAAA", "RESET");
        */
    }

    /*
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
    */
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

    private string GetGameObjectPath(GameObject obj)
    {
        if (obj == null) return "null";
        string path = "/" + obj.name;
        while (obj.transform.parent != null)
        {
            obj = obj.transform.parent.gameObject;
            path = "/" + obj.name + path;
        }
        return path;
    }


    private void DeactivateAllButtonsWithName(Transform parent, string targetName)
    {
        if (parent.name == targetName)
        {
            parent.gameObject.SetActive(false);
            Debug.Log($"[DashboardController] Found and dynamically deactivated '{targetName}' at hierarchy path: {GetGameObjectPath(parent.gameObject)}");
        }
        
        for (int i = 0; i < parent.childCount; i++)
        {
            DeactivateAllButtonsWithName(parent.GetChild(i), targetName);
        }
    }

    private void AutoHealPanelLayout()
    {
        // Layout self-healing deactivated as live dispatch is removed
    }
}