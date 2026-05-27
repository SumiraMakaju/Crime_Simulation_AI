using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public class CameraFix : MonoBehaviour
{
    void Awake()
    {
        // Kill fog completely
        RenderSettings.fog = false;

        // Force dark ambient
        RenderSettings.ambientMode = AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.1f, 0.1f, 0.15f);

        // Kill skybox
        RenderSettings.skybox = null;
    }
}