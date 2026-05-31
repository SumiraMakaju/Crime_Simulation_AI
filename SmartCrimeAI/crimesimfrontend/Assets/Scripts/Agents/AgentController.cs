using System.Collections;
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
    private Dictionary<string, string> _previousStates = new();
    private Dictionary<string, AgentBadge> _badges = new();

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

        // Create floating badge
        var badge = AgentBadge.Create(go.transform, 1.5f);
        _badges[data.id] = badge;

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
                go.transform.position, target, Time.deltaTime * 20f);

            // Face movement direction
            Vector3 dir = (target - go.transform.position).normalized;
            if (dir != Vector3.zero)
                go.transform.rotation = Quaternion.LookRotation(dir);
        }
    }

    private IEnumerator PlayArrestAnimation(string criminalId)
    {
        if (!_agentObjects.TryGetValue(criminalId, out var go)) yield break;

        float elapsed = 0f;
        Vector3 originalScale = go.transform.localScale;

        // Phase 1: Spin fast (caught panic)
        while (elapsed < 0.6f)
        {
            elapsed += Time.deltaTime;
            go.transform.Rotate(0, 720f * Time.deltaTime, 0, Space.World);
            yield return null;
        }

        // Phase 2: Shrink down into ground
        elapsed = 0f;
        while (elapsed < 0.4f)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / 0.4f;
            go.transform.localScale = Vector3.Lerp(originalScale, Vector3.zero, t);
            yield return null;
        }

        // Phase 3: Spawn green flash at position
        GameObject flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        flash.transform.position = go.transform.position + Vector3.up;
        flash.transform.localScale = Vector3.one * 0.5f;
        Destroy(flash.GetComponent<Collider>());
        var flashMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        flashMat.SetFloat("_Surface", 1);
        flashMat.color = new Color(0f, 1f, 0.3f, 0.8f);
        flash.GetComponent<Renderer>().material = flashMat;

        // Expand and fade the flash
        elapsed = 0f;
        while (elapsed < 0.5f)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / 0.5f;
            flash.transform.localScale = Vector3.Lerp(Vector3.one * 0.5f, Vector3.one * 3f, t);
            flashMat.color = new Color(0f, 1f, 0.3f, Mathf.Lerp(0.8f, 0f, t));
            yield return null;
        }

        Destroy(flash);
    }


    private void UpdateVisuals(AgentData data)
    {
        // Update badge
        if (_badges.TryGetValue(data.id, out var badge))
            badge.SetState(data.type, data.state);
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

        // Detect state change to caught/fleeing after committing
        if (_previousStates.TryGetValue(data.id, out var prevState))
        {
            if (prevState == "committing" && data.state == "fleeing")
                StartCoroutine(PlayArrestAnimation(data.id));

            if (prevState == "fleeing" && data.type == "criminal")
            {
                // Criminal disappeared from list = got caught
                // Handled in DespawnAgent instead
            }
        }
        _previousStates[data.id] = data.state;
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
        // If it was a criminal, play arrest animation before destroying
        if (_agentObjects.TryGetValue(id, out var go))
        {
            if (id.StartsWith("crim"))
                StartCoroutine(PlayArrestAndDestroy(id, go));
            else
                Destroy(go);
        }

        _agentObjects.Remove(id);
        _navAgents.Remove(id);
        _sirenLights.Remove(id);
        _agentRenderers.Remove(id);
        _animators.Remove(id);
        _previousStates.Remove(id);

        if (_badges.TryGetValue(id, out var badge))
        {
            if (badge != null) Destroy(badge.gameObject);
            _badges.Remove(id);
        }
    }

    private IEnumerator PlayArrestAndDestroy(string id, GameObject go)
    {
        if (go == null) yield break;

        float elapsed = 0f;

        // Spin
        while (elapsed < 0.6f && go != null)
        {
            elapsed += Time.deltaTime;
            go.transform.Rotate(0, 720f * Time.deltaTime, 0, Space.World);
            yield return null;
        }

        // Shrink
        elapsed = 0f;
        Vector3 originalScale = go != null ? go.transform.localScale : Vector3.one;
        while (elapsed < 0.4f && go != null)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / 0.4f;
            go.transform.localScale = Vector3.Lerp(originalScale, Vector3.zero, t);
            yield return null;
        }

        // Green flash
        Vector3 flashPos = go != null ? go.transform.position + Vector3.up : Vector3.zero;
        if (go != null) Destroy(go);

        GameObject flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        flash.transform.position = flashPos;
        flash.transform.localScale = Vector3.one * 0.3f;
        Destroy(flash.GetComponent<Collider>());

        var flashMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        flashMat.SetFloat("_Surface", 1);
        flashMat.color = new Color(0f, 1f, 0.3f, 0.9f);
        flash.GetComponent<Renderer>().material = flashMat;

        elapsed = 0f;
        while (elapsed < 0.6f)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / 0.6f;
            if (flash != null)
            {
                flash.transform.localScale = Vector3.Lerp(Vector3.one * 0.3f, Vector3.one * 4f, t);
                flashMat.color = new Color(0f, 1f, 0.3f, Mathf.Lerp(0.9f, 0f, t));
            }
            yield return null;
        }

        if (flash != null) Destroy(flash);
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