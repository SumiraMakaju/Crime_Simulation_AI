using UnityEngine;

public class FaceCamera : MonoBehaviour
{
    private Camera _cam;

    void Start()
    {
        _cam = Camera.main;
    }

    void LateUpdate()
    {
        if (_cam == null) return;
        transform.forward = _cam.transform.forward;
    }
}