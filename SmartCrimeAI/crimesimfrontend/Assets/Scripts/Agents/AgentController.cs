using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class AgentController : MonoBehaviour
{
    [Header("Agent Prefabs")]
    public GameObject civilianPrefab;
    public GameObject criminalPrefab;
    public GameObject policePrefab;

    [Header("Parent transform for spawned agents")]
    public Transform agentsParent;

    [Header("Movement")]
    [Tooltip("Must match backend SIMULATION_TICK_SLEEP = 0.5")]
    public float tickRate = 0.5f;
    public float moveSpeed = 12f;

    //  Internal 
    private Dictionary<string, GameObject> _agentObjects = new();
    private Dictionary<string, NavMeshAgent> _navAgents = new();
    private Dictionary<string, Light> _sirenLights = new();
    private Dictionary<string, MinecraftAgentAnimator> _animators = new();
    private Dictionary<string, string> _previousStates = new();
    private Dictionary<string, string> _agentTypes = new();
    private Dictionary<string, Vector3> _targetPositions = new();
    private Dictionary<string, AgentBadge> _badges = new();

    // Arrest animation lock — prevent movement during arrest
    private HashSet<string> _arrestLocked = new();


    public void UpdateAgents(List<AgentData> agents)
    {
        HashSet<string> seenIds = new();

        foreach (var data in agents)
        {
            seenIds.Add(data.id);

            if (!_agentObjects.ContainsKey(data.id))
                SpawnAgent(data);

            // Only update target if not arrest-locked
            if (!_arrestLocked.Contains(data.id))
            {
                _targetPositions[data.id] = new Vector3(data.x, 0f, data.z);
                UpdateVisuals(data);
            }
        }

        // Despawn removed agents
        var toRemove = new List<string>();
        foreach (var id in _agentObjects.Keys)
            if (!seenIds.Contains(id)) toRemove.Add(id);

        foreach (var id in toRemove)
            DespawnAgent(id);
    }


    void Update()
    {
        // Smoothly move every agent toward their backend target position
        foreach (var kvp in _targetPositions)
        {
            string id = kvp.Key;
            Vector3 target = kvp.Value;

            if (!_agentObjects.TryGetValue(id, out var go)) continue;
            if (_arrestLocked.Contains(id)) continue;

            // Use NavMesh if available, otherwise direct lerp
            if (_navAgents.TryGetValue(id, out var nav) && nav.isOnNavMesh)
            {
                nav.speed = moveSpeed;
                if (Vector3.Distance(nav.destination, target) > 0.5f)
                    nav.SetDestination(target);
            }
            else
            {
                // Direct smooth movement — always works
                go.transform.position = Vector3.MoveTowards(
                    go.transform.position,
                    target,
                    moveSpeed * Time.deltaTime);

                // Face direction of movement
                Vector3 dir = (target - go.transform.position).normalized;
                if (dir.magnitude > 0.1f)
                {
                    Quaternion targetRot = Quaternion.LookRotation(new Vector3(dir.x, 0, dir.z));
                    go.transform.rotation = Quaternion.Slerp(
                        go.transform.rotation, targetRot, Time.deltaTime * 10f);
                }
            }
        }
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

        if (prefab == null) return;

        Transform parent = agentsParent != null ? agentsParent : transform;
        Vector3 spawnPos = new Vector3(data.x, 0f, data.z);

        var go = Instantiate(prefab, spawnPos, Quaternion.identity, parent);
        go.name = data.id;
        go.transform.localScale = Vector3.one * 0.5f;

        _agentObjects[data.id] = go;
        _agentTypes[data.id] = data.type;
        _targetPositions[data.id] = spawnPos;
        _previousStates[data.id] = data.state;

        // Cache NavMeshAgent
        var nav = go.GetComponent<NavMeshAgent>();
        if (nav != null)
        {
            nav.speed = moveSpeed;
            nav.angularSpeed = 360f;
            nav.acceleration = 50f;
            nav.stoppingDistance = 0.3f;
            _navAgents[data.id] = nav;
        }

        // Cache siren light (police)
        var siren = go.transform.Find("SirenLight")?.GetComponent<Light>();
        if (siren != null) _sirenLights[data.id] = siren;

        // Cache animator
        var anim = go.GetComponent<MinecraftAgentAnimator>();
        if (anim != null) _animators[data.id] = anim;

        // Create floating badge
        var badge = AgentBadge.Create(go.transform, 1.8f);
        _badges[data.id] = badge;
    }

 
    private void UpdateVisuals(AgentData data)
    {
        string prevState = _previousStates.GetValueOrDefault(data.id, "");
        string agentType = _agentTypes.GetValueOrDefault(data.id, data.type);

     
        if (_animators.TryGetValue(data.id, out var anim))
            anim.SetState(data.state);


        if (_badges.TryGetValue(data.id, out var badge))
            badge.SetState(agentType, data.state);

  
        if (agentType == "criminal")
        {
            // Started committing
            if (data.state == "committing" && prevState != "committing")
                TintAgent(data.id, new Color(1f, 0.1f, 0.1f));

            // Got caught — was committing/fleeing, now laying_low
            if ((prevState == "committing" || prevState == "fleeing")
                && data.state == "laying_low")
            {
                StartCoroutine(PlayArrestAnimation(data.id));
            }

            // Back to scouting — restore color
            if (data.state == "scouting")
                TintAgent(data.id, new Color(0.17f, 0.17f, 0.17f));

            if (data.state == "fleeing")
                TintAgent(data.id, new Color(1f, 0.5f, 0f));
        }

        
        if (agentType == "police" && _sirenLights.TryGetValue(data.id, out var siren))
        {
            if (data.state == "responding")
            {
                float flash = Mathf.Sin(Time.time * 10f);
                siren.intensity = Mathf.Abs(flash) * 4f;
                siren.color = flash > 0
                    ? new Color(0f, 0.3f, 1f)
                    : new Color(1f, 0.1f, 0.1f);
            }
            else
            {
                siren.intensity = Mathf.Lerp(siren.intensity, 0f, Time.deltaTime * 5f);
            }
        }

        _previousStates[data.id] = data.state;
    }


    private IEnumerator PlayArrestAnimation(string id)
    {
        if (!_agentObjects.TryGetValue(id, out var go)) yield break;

        // Lock movement during arrest
        _arrestLocked.Add(id);

        // Stop NavMesh
        if (_navAgents.TryGetValue(id, out var nav) && nav.isOnNavMesh)
            nav.isStopped = true;

        // Set handcuff animation
        if (_animators.TryGetValue(id, out var anim))
            anim.SetState("handcuffed");

        // Flash red
        TintAgent(id, new Color(1f, 0f, 0f));

        // Phase 1: spin fast (0.5s)
        float t = 0f;
        while (t < 0.5f && go != null)
        {
            t += Time.deltaTime;
            go.transform.Rotate(0, 720f * Time.deltaTime, 0);
            yield return null;
        }

        // Phase 2: hands forward crouch (hold 1.5s)
        yield return new WaitForSeconds(1.5f);

        // Phase 3: shrink into ground (0.4s)
        t = 0f;
        Vector3 startScale = go != null ? go.transform.localScale : Vector3.one;
        while (t < 0.4f && go != null)
        {
            t += Time.deltaTime;
            go.transform.localScale = Vector3.Lerp(startScale, Vector3.zero, t / 0.4f);
            yield return null;
        }

        // Green burst
        if (go != null)
        {
            Vector3 pos = go.transform.position + Vector3.up;
            StartCoroutine(SpawnBurst(pos, new Color(0f, 1f, 0.3f)));
            Destroy(go);
        }

        // Cleanup
        _arrestLocked.Remove(id);
        _agentObjects.Remove(id);
        _navAgents.Remove(id);
        _animators.Remove(id);
        _sirenLights.Remove(id);
        _targetPositions.Remove(id);
        _previousStates.Remove(id);
        _agentTypes.Remove(id);
        if (_badges.TryGetValue(id, out var b)) { if (b) Destroy(b.gameObject); _badges.Remove(id); }
    }


    private IEnumerator SpawnBurst(Vector3 pos, Color color)
    {
        var burst = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        burst.transform.position = pos;
        Destroy(burst.GetComponent<Collider>());
        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetFloat("_Surface", 1);
        mat.color = color;
        burst.GetComponent<Renderer>().material = mat;

        float t = 0f;
        while (t < 0.6f)
        {
            t += Time.deltaTime;
            float scale = Mathf.Lerp(0.3f, 4f, t / 0.6f);
            burst.transform.localScale = Vector3.one * scale;
            mat.color = new Color(color.r, color.g, color.b, Mathf.Lerp(1f, 0f, t / 0.6f));
            yield return null;
        }
        Destroy(burst);
    }


    private void TintAgent(string id, Color color)
    {
        if (!_agentObjects.TryGetValue(id, out var go)) return;
        foreach (var r in go.GetComponentsInChildren<Renderer>())
        {
            if (r.material.shader.name.Contains("TextMeshPro")) continue;
            r.material.color = color;
        }
    }


    private void DespawnAgent(string id)
    {
        if (_arrestLocked.Contains(id)) return; // let arrest animation finish

        if (_agentObjects.TryGetValue(id, out var go) && go != null)
        {
            // If criminal disappears it got arrested — play animation
            if (_agentTypes.GetValueOrDefault(id) == "criminal")
            {
                StartCoroutine(PlayArrestAnimation(id));
                return;
            }
            Destroy(go);
        }

        if (_badges.TryGetValue(id, out var b) && b != null) Destroy(b.gameObject);

        _agentObjects.Remove(id);
        _navAgents.Remove(id);
        _sirenLights.Remove(id);
        _animators.Remove(id);
        _previousStates.Remove(id);
        _agentTypes.Remove(id);
        _targetPositions.Remove(id);
        _badges.Remove(id);
        _arrestLocked.Remove(id);
    }
}