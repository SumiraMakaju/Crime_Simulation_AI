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

    // ── Poll intervals  
    [Header("Poll Settings")]
    [Tooltip("Must match backend SIMULATION_TICK_SLEEP (default 0.5)")]
    public float statePollInterval = 0.5f;
    [Tooltip("Metrics and patrol routes update less frequently")]
    public float metricsPollInterval = 2.0f;

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
        while (_isRunning)
        {
            yield return apiClient.GetState(
                onSuccess: OnStateReceived,
                onError: err => Debug.LogWarning($"[SimManager] /state error: {err}")
            );

            yield return new WaitForSeconds(statePollInterval);
        }
    }

     
    // Dispatch state data to all subsystems
 
    private void OnStateReceived(StateResponse state)
    {
        //   1. Agents 
        if (agentController != null)
            agentController.UpdateAgents(state.agents);

        //   2. Zones (heatmap + lighting)  
        if (cityBuilder != null && cityBuilder.IsReady)
        {
            foreach (var zoneData in state.zones)
            {
                if (cityBuilder.ZoneObjects.TryGetValue(zoneData.id, out var zoneGo))
                {
                    var ctrl = zoneGo.GetComponent<ZoneController>();
                    ctrl?.UpdateFromApi(zoneData);
                }
            }
        }

        //   3. Crime events  
        if (crimeEventSpawner != null)
            crimeEventSpawner.ProcessEvents(state.crime_events);

        //   4. Day/night lighting  
        if (dayNightController != null)
            dayNightController.SetTimeOfDay(state.time_of_day);

        //   5. Dashboard sim time  
        if (dashboardController != null)
            dashboardController.UpdateSimTime(state.time_of_day, state.tick);

        //   6. Patrol routes (from state — also fetched separately) ───────
        if (patrolLineRenderer != null && state.patrol_routes != null)
            patrolLineRenderer.UpdateRoutes(state.patrol_routes);

        // Feed crime events to dashboard log
        if (dashboardController != null)
        {
            foreach (var evt in state.crime_events)
                dashboardController.AddCrimeLogEntry(evt);
        }

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

    public void SetPatrolModeGreedy() { if (apiClient) apiClient.SetPatrolMode("greedy"); }
    public void SetPatrolModeAI() { if (apiClient) apiClient.SetPatrolMode("ai"); }
    public void SetPatrolModeRandom() { if (apiClient) apiClient.SetPatrolMode("random"); }
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