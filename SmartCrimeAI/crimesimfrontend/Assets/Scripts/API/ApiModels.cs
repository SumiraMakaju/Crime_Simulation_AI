// ApiModels.cs
// Data classes that mirror every JSON response from the Python backend.
 

using System;
using System.Collections.Generic;

 
[Serializable]
public class StateResponse
{
    public int tick;
    public float time_of_day;
    public List<AgentData> agents;
    public List<ZoneData> zones;
    public Dictionary<string, List<string>> patrol_routes;
    public List<CrimeEventData> crime_events;
}

 

[Serializable]
public class AgentData
{
    public string id;       // e.g. "civ_0", "crim_2", "pol_1"
    public string type;     // "civilian" | "criminal" | "police"
    public string zone;     // e.g. "C3"
    public float x;         // Unity world X position
    public float z;         // Unity world Z position
    public string state;    // see states table below
}

/*  Agent state values per type:
    civilian : "walking"  | "fleeing"
    criminal : "scouting" | "fleeing" | "laying_low" | "committing"
    police   : "patrolling"| "responding"
*/

 

[Serializable]
public class ZoneData
{
    public string id;           // e.g. "C3"
    public string zone_type;    // "residential" | "commercial" | "park" | "intersection"
    public float risk_score;    // 0.0 – 1.0  (ML prediction output)
    public float lighting;      // 0.0 – 1.0  (drops at night for park/intersection)
    public int population;      // civilian count currently in zone
    public int police_count;    // police count currently in zone
    public bool is_hotspot;     // true when risk_score > 0.65
}

 

[Serializable]
public class CrimeEventData
{
    public string id;           // uuid hex string, unique per event
    public string zone;         // zone where crime occurred, e.g. "B2"
    public float time_of_day;   // simulation hour when it happened
    public string type;         // "theft" | "assault" | "vandalism" | "burglary"
    public bool caught;         // true = police intercepted it
}

 

[Serializable]
public class MetricsResponse
{
    public int total_crimes;
    public int total_caught;
    public float catch_rate;          // 0.0 – 1.0
    public float avg_response_time;   // in ticks
    public float patrol_efficiency;   // 0.0 – 1.0
    public string patrol_mode;        // "greedy" | "ai" | "random"
    public MlMetrics ml_metrics;      // null until enough data collected
}

[Serializable]
public class MlMetrics
{
    public float precision;
    public float recall;
    public float f1;
    public float roc_auc;
}
 

[Serializable]
public class ZoneConfig
{
    public int grid_rows;           // always 6
    public int grid_cols;           // always 6
    public int zone_size_units;     // always 10 (Unity world units per zone side)
    public List<ZoneConfigEntry> zones;
}

[Serializable]
public class ZoneConfigEntry
{
    public string zone_id;          // e.g. "C3"
    public string zone_type;        // "residential" | "commercial" | "park" | "intersection"
    public int row;                 // 0–5  (A=0 … F=5)
    public int col;                 // 0–5
    public float world_x;          // col * 10
    public float world_z;          // row * 10
    public List<string> neighbors; // adjacent zone IDs (up to 4)
}
 
[Serializable]
public class ScenarioPayload
{
    // Only populate the field you want to change.
    // Leave all others at their default (null / 0).
    // The backend ignores keys that aren't present.

    public string set_patrol_mode;      // "greedy" | "ai" | "random"
    public int add_police;
    public int remove_police;
    public int set_civilian_count;
    public float time_jump;             // target hour 0.0–24.0
    public bool reset_metrics;

    // Lighting is special — handled separately, see ScenarioLightingPayload below
}

[Serializable]
public class ScenarioLightingPayload
{
    // Use this when posting set_lighting.
    // Either populate "all" OR individual zone keys, not both.
    public SetLightingBody set_lighting;
}

[Serializable]
public class SetLightingBody
{
    public float all;   // set every zone to this value (0.0–1.0)
    // For per-zone lighting, use Newtonsoft JObject directly in ApiClient
}