using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class AgentController : MonoBehaviour
{
    [Header("Agent Prefabs — assign in Inspector")]
    public GameObject civilianPrefab;
    public GameObject criminalPrefab;
    public GameObject policePrefab;

    [Header("Parent transform for spawned agents")]
    public Transform agentsParent;  // drag the Agents GameObject here

    //  Internal tracking 
    private Dictionary<string, GameObject> _agentObjects = new();
    private Dictionary<string, NavMeshAgent> _navAgents = new();
    private Dictionary<string, Light> _sirenLights = new();
    private Dictionary<string, Renderer[]> _agentRenderers = new();
    private Dictionary<string, MinecraftAgentAnimator> _animators = new();

    // State colors for criminal visual feedback
    private static readonly Color ColorScouting = new Color(0.17f, 0.17f, 0.17f);
    private static readonly Color ColorCommitting = new Color(0.85f, 0.10f, 0.10f);
    private static readonly Color ColorFleeing = new Color(0.85f, 0.55f, 0.10f);
    private static readonly Color ColorLayingLow = new Color(0.10f, 0.10f, 0.10f);


    public void UpdateAgents(List<AgentData> agents)
    {
        HashSet<string> seenIds = new();

        foreach (var data in agents)
        {
            seenIds.Add(data.id);

            if (!_agentObjects.ContainsKey(data.id))
                SpawnAgent(data);

            MoveAgent(data);
            UpdateVisuals(data);
        }

        // Remove agents no longer in the API response
        var toRemove = new List<string>();
        foreach (var id in _agentObjects.Keys)
            if (!seenIds.Contains(id)) toRemove.Add(id);

        foreach (var id in toRemove)
            DespawnAgent(id);
    }

    private void SpawnAgent(AgentData data)
    {

        GameObject prefab = data.type switch
        {
            "civilian" => civilianPrefab,
            "criminal" => criminalPrefab,
            "police" => policePrefab,
            _ => civilianPrefab
        };

        if (prefab == null)
        {
            Debug.LogError($"[AgentController] Prefab for type '{data.type}' not assigned!");
            return;
        }

        Transform parent = agentsParent != null ? agentsParent : transform;
        Vector3 spawnPos = new Vector3(data.x, 0f, data.z);

        var go = Instantiate(prefab, spawnPos, Quaternion.identity, parent);
        go.name = data.id;

        _agentObjects[data.id] = go;

        // Cache NavMeshAgent
        var nav = go.GetComponent<NavMeshAgent>();
        if (nav != null) _navAgents[data.id] = nav;

        // Cache siren light (police only)
        var sirenLight = go.transform.Find("SirenLight")?.GetComponent<Light>();
        if (sirenLight != null) _sirenLights[data.id] = sirenLight;


        var anim = go.GetComponent<MinecraftAgentAnimator>();
        if (anim != null) _animators[data.id] = anim;

        // Cache renderers for color changes
        _agentRenderers[data.id] = go.GetComponentsInChildren<Renderer>();
    }


    private void MoveAgent(AgentData data)
    {
        if (!_agentObjects.TryGetValue(data.id, out var go)) return;

        Vector3 target = new Vector3(data.x, 0f, data.z);

        if (_navAgents.TryGetValue(data.id, out var nav) && nav.isOnNavMesh)
        {
            // Only set destination if agent isn't already heading there
            // (avoids constant recalculation)
            if (Vector3.Distance(nav.destination, target) > 0.5f)
                nav.SetDestination(target);
        }
        else
        {
            // Fallback direct movement — used when NavMesh isn't ready yet
            go.transform.position = Vector3.MoveTowards(
                go.transform.position, target, Time.deltaTime * 5f);

            // Face movement direction
            Vector3 dir = (target - go.transform.position).normalized;
            if (dir != Vector3.zero)
                go.transform.rotation = Quaternion.LookRotation(dir);
        }
    }


    private void UpdateVisuals(AgentData data)
    {
        // Drive the Minecraft animator
        if (_animators.TryGetValue(data.id, out var anim))
            anim.SetState(data.state);

        switch (data.type)
        {
            case "criminal":
                UpdateCriminalVisuals(data);
                break;
            case "police":
                UpdatePoliceVisuals(data);
                break;
        }
    }


    private void UpdateCriminalVisuals(AgentData data)
    {
        if (!_agentRenderers.TryGetValue(data.id, out var renderers)) return;

        // Change body color based on criminal state
        Color targetColor = data.state switch
        {
            "committing" => ColorCommitting,  // red — actively committing crime
            "fleeing" => ColorFleeing,     // orange — running away
            "laying_low" => ColorLayingLow,   // near black — hiding
            _ => ColorScouting     // dark grey — default scouting
        };

        foreach (var r in renderers)
        {
            // Only recolor the Body and Head, not the Hood
            if (r.gameObject.name is "Body" or "Head")
                r.material.color = Color.Lerp(r.material.color, targetColor, Time.deltaTime * 5f);
        }
    }


    private void UpdatePoliceVisuals(AgentData data)
    {
        if (!_sirenLights.TryGetValue(data.id, out var siren)) return;

        bool isResponding = data.state == "responding";

        if (isResponding)
        {
            // Flash siren: blue/red alternating using sine wave
            float flash = Mathf.Sin(Time.time * 10f);
            siren.intensity = Mathf.Abs(flash) * 4f;
            siren.color = flash > 0 ? new Color(0f, 0.3f, 1f) : new Color(1f, 0.1f, 0.1f);
        }
        else
        {
            // Siren off when patrolling
            siren.intensity = Mathf.Lerp(siren.intensity, 0f, Time.deltaTime * 5f);
        }
    }


    private void DespawnAgent(string id)
    {
        if (_agentObjects.TryGetValue(id, out var go))
            Destroy(go);

        _agentObjects.Remove(id);
        _navAgents.Remove(id);
        _sirenLights.Remove(id);
        _animators.Remove(id);
        _agentRenderers.Remove(id);
    }


    public Vector3 GetAgentPosition(string agentId)
    {
        if (_agentObjects.TryGetValue(agentId, out var go))
            return go.transform.position;
        return Vector3.zero;
    }


    public (int civilians, int criminals, int police) GetAgentCounts()
    {
        int c = 0, cr = 0, p = 0;
        foreach (var id in _agentObjects.Keys)
        {
            if (id.StartsWith("civ")) c++;
            else if (id.StartsWith("crim")) cr++;
            else if (id.StartsWith("pol")) p++;
        }
        return (c, cr, p);
    }
}