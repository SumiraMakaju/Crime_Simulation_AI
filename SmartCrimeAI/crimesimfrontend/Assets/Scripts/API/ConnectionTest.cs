using UnityEngine;

public class ConnectionTest : MonoBehaviour
{
    private ApiClient _api;

    void Start()
    {
        _api = GetComponent<ApiClient>();
        StartCoroutine(_api.TestConnection(
            onSuccess: () => Debug.Log("SUCCESS — backend is running"),
            onFail: msg => Debug.LogError($"FAILED — {msg}")
        ));
    }
}