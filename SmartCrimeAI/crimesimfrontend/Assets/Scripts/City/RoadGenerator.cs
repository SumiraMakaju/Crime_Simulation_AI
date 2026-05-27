using UnityEngine;

public class RoadGenerator : MonoBehaviour
{
    [Header("Road Settings")]
    public Material roadMaterial;
    public float roadWidth = 1.5f;
    public float roadHeight = 0.05f;  // just above ground
    public GameObject streetLampPrefab; // assign in Inspector

   
    private CityBuilder _cityBuilder;

 
    void Start()
    {
        _cityBuilder = FindFirstObjectByType<CityBuilder>();
        if (_cityBuilder == null) return;

        // Wait one frame for CityBuilder to finish
        StartCoroutine(GenerateAfterBuild());
    }

    private System.Collections.IEnumerator GenerateAfterBuild()
    {
        yield return new WaitUntil(() => _cityBuilder.IsReady);
        GenerateRoads();
    }

    private void GenerateRoads()
    {
        int rows = 6;
        int cols = 6;
        int zoneSize = 10;

       
        for (int r = 0; r <= rows; r++)
        {
            GameObject road = GameObject.CreatePrimitive(PrimitiveType.Cube);
            road.name = $"RoadH_{r}";
            road.transform.SetParent(transform);
            Destroy(road.GetComponent<Collider>());

            float zPos = r * zoneSize;
            road.transform.position = new Vector3(
                (cols * zoneSize) / 2f, roadHeight, zPos);
            road.transform.localScale = new Vector3(
                cols * zoneSize, 0.05f, roadWidth);

            AssignRoadMaterial(road);
        }

        for (int c = 0; c <= cols; c++)
        {
            GameObject road = GameObject.CreatePrimitive(PrimitiveType.Cube);
            road.name = $"RoadV_{c}";
            road.transform.SetParent(transform);
            Destroy(road.GetComponent<Collider>());

            float xPos = c * zoneSize;
            road.transform.position = new Vector3(
                xPos, roadHeight, (rows * zoneSize) / 2f);
            road.transform.localScale = new Vector3(
                roadWidth, 0.05f, rows * zoneSize);

            AssignRoadMaterial(road);
        }

        GenerateCenterLines(rows, cols, zoneSize);

        PlaceStreetLamps(rows, cols, zoneSize);

        Debug.Log("[RoadGenerator] Roads generated.");
    }

    
    private void GenerateCenterLines(int rows, int cols, int zoneSize)
    {
        Material lineMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        lineMat.color = new Color(0.9f, 0.8f, 0.1f, 1f); // yellow dashes

        // Horizontal center lines
        for (int r = 0; r <= rows; r++)
        {
            for (int c = 0; c < cols; c++)
            {
                GameObject dash = GameObject.CreatePrimitive(PrimitiveType.Cube);
                dash.name = $"Dash_H_{r}_{c}";
                dash.transform.SetParent(transform);
                Destroy(dash.GetComponent<Collider>());

                dash.transform.position = new Vector3(
                    c * zoneSize + zoneSize / 2f, roadHeight + 0.01f, r * zoneSize);
                dash.transform.localScale = new Vector3(2f, 0.01f, 0.1f);
                dash.GetComponent<Renderer>().material = lineMat;
            }
        }

        // Vertical center lines
        for (int c = 0; c <= cols; c++)
        {
            for (int r = 0; r < rows; r++)
            {
                GameObject dash = GameObject.CreatePrimitive(PrimitiveType.Cube);
                dash.name = $"Dash_V_{c}_{r}";
                dash.transform.SetParent(transform);
                Destroy(dash.GetComponent<Collider>());

                dash.transform.position = new Vector3(
                    c * zoneSize, roadHeight + 0.01f, r * zoneSize + zoneSize / 2f);
                dash.transform.localScale = new Vector3(0.1f, 0.01f, 2f);
                dash.GetComponent<Renderer>().material = lineMat;
            }
        }
    }
    private void PlaceStreetLamps(int rows, int cols, int zoneSize)
    {
        if (streetLampPrefab == null) return;

        // Place a lamp at every zone corner
        for (int r = 0; r <= rows; r++)
        {
            for (int c = 0; c <= cols; c++)
            {
                Vector3 pos = new Vector3(
                    c * zoneSize, 0f, r * zoneSize);

                Instantiate(streetLampPrefab, pos,
                    Quaternion.identity, transform);
            }
        }
    }

    private void AssignRoadMaterial(GameObject road)
    {
        var r = road.GetComponent<Renderer>();
        if (roadMaterial != null)
        {
            r.material = roadMaterial;
            return;
        }

        // Default dark asphalt material
        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.color = new Color(0.08f, 0.08f, 0.08f);
        r.material = mat;
    }
}