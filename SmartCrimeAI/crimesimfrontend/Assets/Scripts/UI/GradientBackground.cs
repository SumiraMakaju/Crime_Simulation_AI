using UnityEngine;
using UnityEngine.UI;

[RequireComponent(typeof(RawImage))]
public class GradientBackground : MonoBehaviour
{
    public Color topColor = new Color(0.027f, 0.639f, 0.698f);
    public Color bottomColor = new Color(0.851f, 0.925f, 0.780f);

    void Awake()
    {
        // Force stretch to fill entire canvas
        var rect = GetComponent<RectTransform>();
        rect.anchorMin = Vector2.zero;
        rect.anchorMax = Vector2.one;
        rect.offsetMin = Vector2.zero;
        rect.offsetMax = Vector2.zero;

        // Build gradient texture
        var tex = new Texture2D(1, 256);
        tex.wrapMode = TextureWrapMode.Clamp;
        for (int i = 0; i < 256; i++)
        {
            float t = i / 255f;
            tex.SetPixel(0, i, Color.Lerp(bottomColor, topColor, t));
        }
        tex.Apply();
        GetComponent<RawImage>().texture = tex;
    }
}