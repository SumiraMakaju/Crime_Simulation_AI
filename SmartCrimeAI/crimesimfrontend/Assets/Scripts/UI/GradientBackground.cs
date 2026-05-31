using UnityEngine;
using UnityEngine.UI;

[RequireComponent(typeof(RawImage))]
public class GradientBackground : MonoBehaviour
{
    public Color topColor = new Color(0.027f, 0.639f, 0.698f); // #07A3B2
    public Color bottomColor = new Color(0.851f, 0.925f, 0.780f); // #D9ECC7

    void Start()
    {
        var tex = new Texture2D(1, 256);
        for (int i = 0; i < 256; i++)
        {
            float t = i / 255f;
            tex.SetPixel(0, i, Color.Lerp(bottomColor, topColor, t));
        }
        tex.Apply();
        GetComponent<RawImage>().texture = tex;
    }
}