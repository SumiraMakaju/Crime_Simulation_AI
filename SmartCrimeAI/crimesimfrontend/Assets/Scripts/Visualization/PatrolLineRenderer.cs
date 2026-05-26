using System.Collections.Generic;
using UnityEngine;

public class PatrolLineRenderer : MonoBehaviour
{
    [Header("Line Settings")]
    public Material patrolLineMaterial;
    public float lineWidth = 0.2f;
    public float lineHeightY = 0.3f;   // raised above ground to avoid z-fighting
    public float animationSpeed = 1.5f;   // scroll speed of the line texture

    // One color per police unit — cycles if more than 4 police
    private readonly Color[] _routeColors = new Color[]
    {
        new Color(0.20f, 0.60f, 1.00f, 0.9f),  // blue
        new Color(0.20f, 1.00f, 0.60f, 0.9f),  // green
        new Color(1.00f, 0.80f, 0.20f, 0.9f),  // yellow
        new Color(0.80f, 0.30f, 1.00f, 0.9f),  // purple
        new Color(1.00f, 0.40f, 0.20f, 0.9f),  // orange
    };

    private Dictionary<string, LineRenderer> _lineRenderers = new();
    private Dictionary<string, Color> _lineColors = new();
    private CityBuilder _cityBuilder;
    private int _colorIndex = 0;


    void Awake()
    {
        _cityBuilder = FindObjectOfType<CityBuilder>();

        if (patrolLineMaterial == null)
            CreateDefaultLineMaterial();
    }

    void Update()
    {
        // Animate line texture scrolling for a "moving patrol" feel
        if (patrolLineMaterial != null)
        {
            float offset = Time.time * animationSpeed;
            patrolLineMaterial.SetTextureOffset("_MainTex",
                new Vector2(offset, 0));
        }
    }

 
    public void UpdateRoutes(Dictionary<string, List<string>> routes)
    {
        if (routes == null || routes.Count == 0)
        {
            ClearAllLines();
            return;
        }

        HashSet<string> seenIds = new();

        foreach (var kvp in routes)
        {
            string policeId = kvp.Key;
            List<string> zoneIds = kvp.Value;

            seenIds.Add(policeId);

            // Create LineRenderer if this police unit is new
            if (!_lineRenderers.ContainsKey(policeId))
                CreateLineRenderer(policeId);

            // Build world positions from zone centers
            var positions = BuildPositions(zoneIds);
            if (positions.Count < 2)
            {
                // Not enough points to draw a line — hide it
                _lineRenderers[policeId].positionCount = 0;
                continue;
            }

            var lr = _lineRenderers[policeId];
            lr.positionCount = positions.Count;
            lr.SetPositions(positions.ToArray());
        }

        // Remove lines for police that no longer exist
        var toRemove = new List<string>();
        foreach (var id in _lineRenderers.Keys)
            if (!seenIds.Contains(id)) toRemove.Add(id);

        foreach (var id in toRemove)
            RemoveLine(id);
    }

    private List<Vector3> BuildPositions(List<string> zoneIds)
    {
        var positions = new List<Vector3>();

        foreach (var zoneId in zoneIds)
        {
            if (_cityBuilder == null) break;

            if (_cityBuilder.ZoneConfigs.TryGetValue(zoneId, out var cfg))
            {
                // Use zone center (world_x + 5, world_z + 5)
                positions.Add(new Vector3(
                    cfg.world_x + 5f,
                    lineHeightY,
                    cfg.world_z + 5f));
            }
        }

        // Close the loop — connect last zone back to first
        if (positions.Count > 2)
            positions.Add(positions[0]);

        return positions;
    }

    private void CreateLineRenderer(string policeId)
    {
        var go = new GameObject($"PatrolLine_{policeId}");
        go.transform.SetParent(transform);

        var lr = go.AddComponent<LineRenderer>();

        // Assign color — cycle through palette
        Color color = _routeColors[_colorIndex % _routeColors.Length];
        _colorIndex++;
        _lineColors[policeId] = color;

        lr.material = patrolLineMaterial != null
                               ? new Material(patrolLineMaterial)
                               : CreateDefaultLineMaterial();
        lr.startColor = color;
        lr.endColor = new Color(color.r, color.g, color.b, 0.3f);
        lr.startWidth = lineWidth;
        lr.endWidth = lineWidth * 0.5f;
        lr.loop = false;
        lr.useWorldSpace = true;
        lr.numCornerVertices = 4;   // smooth corners
        lr.numCapVertices = 4;   // smooth ends
        lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lr.receiveShadows = false;

        _lineRenderers[policeId] = lr;
    }

    private void RemoveLine(string policeId)
    {
        if (_lineRenderers.TryGetValue(policeId, out var lr))
            Destroy(lr.gameObject);

        _lineRenderers.Remove(policeId);
        _lineColors.Remove(policeId);
    }

    private void ClearAllLines()
    {
        foreach (var id in new List<string>(_lineRenderers.Keys))
            RemoveLine(id);
    }

    private Material CreateDefaultLineMaterial()
    {
        // Fallback material if none assigned in Inspector
        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.color = Color.white;
        patrolLineMaterial = mat;
        return mat;
    }
}