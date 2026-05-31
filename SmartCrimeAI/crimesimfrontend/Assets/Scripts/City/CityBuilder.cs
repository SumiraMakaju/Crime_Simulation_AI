// CityBuilder.cs
// Reads zone_config.json written by the Python backend and spawns
// the correct zone prefab at each world position.

using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

public class CityBuilder : MonoBehaviour
{
    [Header("Zone Prefabs � assign all 4 in Inspector")]
    public GameObject residentialPrefab;
    public GameObject commercialPrefab;
    public GameObject parkPrefab;
    public GameObject intersectionPrefab;
    public bool IsReady { get; private set; } = false;

    [Header("Parent transform for all spawned zones")]
    public Transform cityParent;   // drag the City GameObject here

    [Header("Path to zone_config.json")]
    [Tooltip("Relative to the backend/ folder. Adjust if your folder structure differs.")]
    public string zoneConfigRelativePath = "../../../../backend/shared/zone_config.json";


    public Dictionary<string, GameObject> ZoneObjects = new();
    public Dictionary<string, ZoneConfigEntry> ZoneConfigs = new();


    private bool _built = false;


    //void Start()
    //{
    //    BuildCity();
   // }

    void Awake()
    {
        BuildCity();
    }

    public void BuildCity()
    {
        if (_built)
        {
            Debug.LogWarning("[CityBuilder] BuildCity called twice � skipping.");
            return;
        }


        // Application.dataPath  →  .../crimesimfrontend/Assets
        // Walk up to the solution root (parent of crimesimfrontend), then into backend/shared
        string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string solutionRoot = Path.GetFullPath(Path.Combine(projectRoot, ".."));
        string fullPath = Path.Combine(solutionRoot, "backend", "shared", "zone_config.json");
        fullPath = Path.GetFullPath(fullPath);

        Debug.Log($"[CityBuilder] Resolved zone_config.json path:\n{fullPath}");

        if (!File.Exists(fullPath))
        {
            Debug.LogError(
                $"[CityBuilder] zone_config.json not found at:\n{fullPath}\n" +
                "Make sure the Python backend is running before pressing Play.");
            return;
        }


        ZoneConfig config;
        try
        {
            string json = File.ReadAllText(fullPath);
            config = JsonConvert.DeserializeObject<ZoneConfig>(json);
        }
        catch (Exception e)
        {
            Debug.LogError($"[CityBuilder] Failed to parse zone_config.json: {e.Message}");
            return;
        }

        if (config?.zones == null || config.zones.Count == 0)
        {
            Debug.LogError("[CityBuilder] zone_config.json parsed but zones list is empty.");
            return;
        }


        Transform parent = cityParent != null ? cityParent : transform;

        foreach (var zoneCfg in config.zones)
        {
            GameObject prefab = zoneCfg.zone_type switch
            {
                "residential" => residentialPrefab,
                "commercial" => commercialPrefab,
                "park" => parkPrefab,
                "intersection" => intersectionPrefab,
                _ => residentialPrefab   // safe fallback
            };

            if (prefab == null)
            {
                Debug.LogError(
                    $"[CityBuilder] Prefab for zone type '{zoneCfg.zone_type}' is not assigned!");
                continue;
            }

            // Zone origin is bottom-left corner � prefab content is already
            // offset +5 on X and Z so everything centers correctly
            Vector3 pos = new Vector3(zoneCfg.world_x, 0f, zoneCfg.world_z);

            GameObject zone = Instantiate(prefab, pos, Quaternion.identity, parent);
            zone.name = $"Zone_{zoneCfg.zone_id}";

            // Attach ZoneController for runtime API updates
            var ctrl = zone.AddComponent<ZoneController>();
            ctrl.ZoneId = zoneCfg.zone_id;
            ctrl.ZoneType = zoneCfg.zone_type;

            // Register in lookup dictionaries
            ZoneObjects[zoneCfg.zone_id] = zone;
            ZoneConfigs[zoneCfg.zone_id] = zoneCfg;
        }

        _built = true;
        Debug.Log($"[CityBuilder] Built {ZoneObjects.Count} zones successfully.");

        _built = true;
        IsReady = true;  // add this line
        Debug.Log($"[CityBuilder] Built {ZoneObjects.Count} zones successfully.");
       
        BakeNavMesh();
        Debug.Log($"[CityBuilder] Zone keys loaded: {string.Join(", ", ZoneConfigs.Keys)}");
    }

    private void BakeNavMesh()
    {
        var surface = FindObjectOfType<Unity.AI.Navigation.NavMeshSurface>();
        if (surface != null)
        {
            surface.BuildNavMesh();
            Debug.Log("[CityBuilder] NavMesh baked.");
        }
        else
        {
            Debug.LogWarning("[CityBuilder] No NavMeshSurface found � NavMesh not baked. " +
                             "Add a NavMeshSurface component to the scene.");
        }
    }
}