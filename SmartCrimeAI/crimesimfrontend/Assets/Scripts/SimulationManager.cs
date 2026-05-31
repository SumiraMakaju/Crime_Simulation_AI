using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class SimulationManager : MonoBehaviour
{
    //   Subsystem References — assign all in Inspector  
    [Header("Core Systems")]
    public ApiClient apiClient;
    public CityBuilder cityBuilder;
    public AgentController agentController;

    [Header("Visualization Systems")]
    public PatrolLineRenderer patrolLineRenderer;
    public CrimeEventSpawner crimeEventSpawner;
    public DayNightController dayNightController;

    [Header("UI")]
    public DashboardController dashboardController;

    public void SetPatrolModeMARL() { Debug.Log($"[SimulationManager] SetPatrolModeMARL called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.SetPatrolModeMARL(); }
    public void TriggerBlackout() { Debug.Log($"[SimulationManager] TriggerBlackout called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.TriggerBlackout(); }
    public void TriggerSaturation() { Debug.Log($"[SimulationManager] TriggerSaturation called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.TriggerSaturation(); }
    public void TriggerRecovery() { Debug.Log($"[SimulationManager] TriggerRecovery called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.TriggerRecovery(); }

    [Header("Poll Settings")]
    [Tooltip("Must match backend SIMULATION_TICK_SLEEP (default 3.0)")]
    public float statePollInterval = 3.0f;
    [Tooltip("Metrics and patrol routes update less frequently")]
    public float metricsPollInterval = 6.0f;

    //   Startup delay  
    [Tooltip("Seconds to wait after Play before starting polls. " +
             "Gives CityBuilder time to finish spawning zones.")]
    public float startupDelay = 2.0f;

    //   Internal state  
    private bool _isRunning = false;
    private int _lastTick = -1;
    private bool _backendOnline = false;

    //   Connection status UI (optional)  
    [Header("Connection Status (optional)")]
    public TextMeshProUGUI connectionStatusText;
    void Start()
    {
        // Auto-heal unassigned components dynamically at startup
        if (apiClient == null) { apiClient = FindObjectOfType<ApiClient>(); if (apiClient != null) Debug.Log($"[SimulationManager] Auto-healed unassigned apiClient to: {apiClient.gameObject.name}"); }
        if (dashboardController == null) { dashboardController = FindObjectOfType<DashboardController>(); if (dashboardController != null) Debug.Log($"[SimulationManager] Auto-healed unassigned dashboardController to: {dashboardController.gameObject.name}"); }
        if (agentController == null) { agentController = FindObjectOfType<AgentController>(); if (agentController != null) Debug.Log($"[SimulationManager] Auto-healed unassigned agentController to: {agentController.gameObject.name}"); }
        if (cityBuilder == null) { cityBuilder = FindObjectOfType<CityBuilder>(); if (cityBuilder != null) Debug.Log($"[SimulationManager] Auto-healed unassigned cityBuilder to: {cityBuilder.gameObject.name}"); }
        if (crimeEventSpawner == null) { crimeEventSpawner = FindObjectOfType<CrimeEventSpawner>(); if (crimeEventSpawner != null) Debug.Log($"[SimulationManager] Auto-healed unassigned crimeEventSpawner to: {crimeEventSpawner.gameObject.name}"); }
        if (dayNightController == null) { dayNightController = FindObjectOfType<DayNightController>(); if (dayNightController != null) Debug.Log($"[SimulationManager] Auto-healed unassigned dayNightController to: {dayNightController.gameObject.name}"); }
        if (patrolLineRenderer == null) { patrolLineRenderer = FindObjectOfType<PatrolLineRenderer>(); if (patrolLineRenderer != null) Debug.Log($"[SimulationManager] Auto-healed unassigned patrolLineRenderer to: {patrolLineRenderer.gameObject.name}"); }

        ValidateReferences();
        StartCoroutine(Startup());
    }
 
    // Startup sequence
    
    private IEnumerator Startup()
    {
        SetConnectionStatus("Connecting to backend...", Color.yellow);

        // Step 1: test backend connection
        bool connected = false;
        yield return apiClient.TestConnection(
            onSuccess: () => connected = true,
            onFail: msg =>
            {
                SetConnectionStatus("Backend offline — start python main.py", Color.red);
                Debug.LogError($"[SimManager] {msg}");
            }
        );

        if (!connected) yield break;

        _backendOnline = true;
        SetConnectionStatus("Backend online", Color.green);

        // Step 2: wait for CityBuilder to finish
        yield return new WaitForSeconds(startupDelay);

        // Step 3: start poll loops
        _isRunning = true;
        StartCoroutine(PollState());
        StartCoroutine(PollMetricsAndRoutes());

        Debug.Log("[SimManager] Poll loops started.");
    }

 
    // Poll /state every 0.5s
 
    private IEnumerator PollState()
    {
        Debug.Log($"[SimulationManager] PollState loop started. Interval: {statePollInterval}s");
        while (_isRunning)
        {
            yield return apiClient.GetState(
                onSuccess: state => {
                    Debug.Log($"[SimulationManager] /state poll successful. Tick: {state.tick}, Time: {state.time_of_day:F2}, Agents: {state.agents?.Count ?? 0}, Zones: {state.zones?.Count ?? 0}, Crimes: {state.crime_events?.Count ?? 0}");
                    OnStateReceived(state);
                },
                onError: err => Debug.LogError($"[SimulationManager] /state poll error: {err}")
            );

            yield return new WaitForSeconds(statePollInterval);
        }
    }

    private void OnStateReceived(StateResponse state)
    {
        if (state == null)
        {
            Debug.LogError("[SimulationManager] OnStateReceived: state is null!");
            return;
        }

        //   1. Agents 
        if (agentController != null)
        {
            Debug.Log($"[SimulationManager] Updating {state.agents?.Count ?? 0} agents.");
            agentController.UpdateAgents(state.agents);
        }
        else
        {
            Debug.LogWarning("[SimulationManager] AgentController reference is missing!");
        }

        //   2. Zones (heatmap + lighting)  
        if (cityBuilder != null && cityBuilder.IsReady)
        {
            int zoneUpdateCount = 0;
            foreach (var zoneData in state.zones)
            {
                if (cityBuilder.ZoneObjects.TryGetValue(zoneData.id, out var zoneGo))
                {
                    var ctrl = zoneGo.GetComponent<ZoneController>();
                    if (ctrl != null)
                    {
                        ctrl.UpdateFromApi(zoneData);
                        zoneUpdateCount++;
                    }
                }
            }
            Debug.Log($"[SimulationManager] Updated {zoneUpdateCount} zones.");
        }
        else
        {
            Debug.LogWarning($"[SimulationManager] CityBuilder reference missing or not ready. Ready={cityBuilder?.IsReady}");
        }

        //   3. Crime events  
        if (crimeEventSpawner != null)
        {
            Debug.Log($"[SimulationManager] Spawning/updating {state.crime_events?.Count ?? 0} crime events.");
            crimeEventSpawner.ProcessEvents(state.crime_events, state.tick);
        }
        else
        {
            Debug.LogWarning("[SimulationManager] CrimeEventSpawner reference is missing!");
        }

        //   4. Day/night lighting  
        if (dayNightController != null)
            dayNightController.SetTimeOfDay(state.time_of_day);

        //   5. Dashboard sim time  
        if (dashboardController != null)
            dashboardController.UpdateSimTime(state.time_of_day, state.tick);

        //   6. Patrol routes (from state — also fetched separately) 
        if (patrolLineRenderer != null && state.patrol_routes != null)
            patrolLineRenderer.UpdateRoutes(state.patrol_routes);


        if (dashboardController != null)
        {
            dashboardController.UpdateSimTime(state.time_of_day, state.tick);
            dashboardController.UpdateScenario(state.active_scenario);
        }

        if (state.tick == _lastTick) return; // skip duplicate ticks 
        _lastTick = state.tick;
    }
 
    // Poll /metrics and /patrol-routes every 2s
  
    private IEnumerator PollMetricsAndRoutes()
    {
        while (_isRunning)
        {
            yield return new WaitForSeconds(metricsPollInterval);

            // Metrics
            yield return apiClient.GetMetrics(
                onSuccess: metrics =>
                {
                    if (dashboardController != null)
                        dashboardController.UpdateMetrics(metrics);
                },
                onError: err => Debug.LogWarning($"[SimManager] /metrics error: {err}")
            );

            // Patrol routes
            yield return apiClient.GetPatrolRoutes(
                onSuccess: routes =>
                {
                    if (patrolLineRenderer != null)
                        patrolLineRenderer.UpdateRoutes(routes);
                },
                onError: err => Debug.LogWarning($"[SimManager] /patrol-routes error: {err}")
            );
        }
    }

    // Public scenario controls — called by UI buttons

    public void SetPatrolModeGreedy() { Debug.Log($"[SimulationManager] SetPatrolModeGreedy called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.SetPatrolMode("greedy"); }
    public void SetPatrolModeAI() { Debug.Log($"[SimulationManager] SetPatrolModeAI called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.SetPatrolMode("ai"); }
    public void SetPatrolModeRandom() { Debug.Log($"[SimulationManager] SetPatrolModeRandom called. apiClient is {(apiClient != null ? "not null" : "null")}"); if (apiClient) apiClient.SetPatrolMode("random"); }
    public void AddOnePolice() { if (apiClient) apiClient.AddPolice(1); }
    public void RemoveOnePolice() { if (apiClient) apiClient.RemovePolice(1); }
    public void SetLightingDay() { if (apiClient) apiClient.SetLightingAll(1.0f); }
    public void SetLightingNight() { if (apiClient) apiClient.SetLightingAll(0.2f); }
    public void JumpToNoon() { if (apiClient) apiClient.JumpToHour(12f); }
    public void JumpToMidnight() { if (apiClient) apiClient.JumpToHour(0f); }
    public void ResetMetrics() { if (apiClient) apiClient.ResetMetrics(); }


   
    // Helpers
 
    private void SetConnectionStatus(string msg, Color color)
    {
        if (connectionStatusText != null)
        {
            connectionStatusText.text = msg;
            connectionStatusText.color = color;
        }
        Debug.Log($"[SimManager] {msg}");
    }

    private void ValidateReferences()
    {
        if (apiClient == null) Debug.LogError("[SimManager] ApiClient not assigned!");
        if (cityBuilder == null) Debug.LogError("[SimManager] CityBuilder not assigned!");
        if (agentController == null) Debug.LogError("[SimManager] AgentController not assigned!");

        // These are warnings not errors — sim runs without them
        if (patrolLineRenderer == null) Debug.LogWarning("[SimManager] PatrolLineRenderer not assigned.");
        if (crimeEventSpawner == null) Debug.LogWarning("[SimManager] CrimeEventSpawner not assigned.");
        if (dayNightController == null) Debug.LogWarning("[SimManager] DayNightController not assigned.");
        if (dashboardController == null) Debug.LogWarning("[SimManager] DashboardController not assigned.");
    }

    void OnDestroy()
    {
        _isRunning = false;
    }
}