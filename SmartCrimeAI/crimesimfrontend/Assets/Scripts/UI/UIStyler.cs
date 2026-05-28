using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class UIStyler : MonoBehaviour
{
    void Start()
    {
        StyleAllPanels();
        StyleAllButtons();
    }

    private void StyleAllPanels()
    {
        // Top Bar
        StylePanel("TopBar",
            new Color(0.04f, 0.06f, 0.12f, 0.96f),
            addGradientLine: true,
            lineColor: new Color(0.3f, 0.6f, 1.0f));

        // Metrics Panel
        StylePanel("MetricsPanel",
            new Color(0.04f, 0.06f, 0.12f, 0.93f),
            addGradientLine: true,
            lineColor: new Color(0.3f, 0.6f, 1.0f));

        // Scenario Panel
        StylePanel("ScenarioPanel",
            new Color(0.04f, 0.06f, 0.12f, 0.93f),
            addGradientLine: true,
            lineColor: new Color(0.5f, 0.3f, 1.0f));

        // Crime Log Panel
        StylePanel("CrimeLogPanel",
            new Color(0.04f, 0.06f, 0.12f, 0.93f),
            addGradientLine: true,
            lineColor: new Color(1.0f, 0.3f, 0.3f));
    }
    
    private void StylePanel(string panelName, Color bgColor,
        bool addGradientLine = false, Color lineColor = default)
    {
        var panel = GameObject.Find(panelName);
        if (panel == null) return;

        // Background
        var img = panel.GetComponent<Image>();
        if (img == null) img = panel.AddComponent<Image>();
        img.color = bgColor;

        // Rounded corners via sprite (use Unity's built-in rounded rect)
        img.sprite = CreateRoundedSprite();
        img.type = Image.Type.Sliced;

        // Accent line at top of panel
        if (addGradientLine)
        {
            var lineGo = new GameObject("AccentLine");
            lineGo.transform.SetParent(panel.transform, false);

            var lineRect = lineGo.AddComponent<RectTransform>();
            lineRect.anchorMin = new Vector2(0, 1);
            lineRect.anchorMax = new Vector2(1, 1);
            lineRect.pivot = new Vector2(0.5f, 1);
            lineRect.offsetMin = new Vector2(8, -3);
            lineRect.offsetMax = new Vector2(-8, 0);
            lineRect.sizeDelta = new Vector2(0, 3);

            var lineImg = lineGo.AddComponent<Image>();
            lineImg.color = lineColor;
        }
    }

    private void StyleAllButtons()
    {
        StyleSingleButton("BtnGreedy",
            new Color(0.10f, 0.30f, 0.80f),
            new Color(0.20f, 0.50f, 1.00f),
            "GREEDY PATROL");

        StyleSingleButton("BtnAI",
            new Color(0.35f, 0.10f, 0.70f),
            new Color(0.60f, 0.30f, 1.00f),
            "AI PATROL");

        StyleSingleButton("BtnAddPolice",
            new Color(0.05f, 0.40f, 0.20f),
            new Color(0.10f, 0.80f, 0.40f),
            "+ ADD POLICE");

        StyleSingleButton("BtnRemovePolice",
            new Color(0.50f, 0.08f, 0.08f),
            new Color(1.00f, 0.25f, 0.25f),
            "- REMOVE POLICE");

        StyleSingleButton("BtnLightingDay",
            new Color(0.50f, 0.38f, 0.00f),
            new Color(1.00f, 0.78f, 0.10f),
            "SET DAY");

        StyleSingleButton("BtnLightingNight",
            new Color(0.05f, 0.05f, 0.25f),
            new Color(0.20f, 0.20f, 0.80f),
            "SET NIGHT");
    }

    private void StyleSingleButton(string btnName, Color bgColor,
        Color glowColor, string labelText)
    {
        var btnGo = GameObject.Find(btnName);
        if (btnGo == null) return;

        var btn = btnGo.GetComponent<Button>();
        if (btn == null) return;

        //  Background image 
        var img = btnGo.GetComponent<Image>();
        img.color = bgColor;
        img.sprite = CreateRoundedSprite();
        img.type = Image.Type.Sliced;

        //  Color transition on hover/press 
        var colors = btn.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = new Color(1.3f, 1.3f, 1.3f, 1f);
        colors.pressedColor = new Color(0.7f, 0.7f, 0.7f, 1f);
        colors.selectedColor = Color.white;
        colors.fadeDuration = 0.1f;
        btn.colors = colors;

        //  Label 
        var tmp = btnGo.GetComponentInChildren<TextMeshProUGUI>();
        if (tmp != null)
        {
            tmp.text = labelText;
            tmp.color = Color.white;
            tmp.fontSize = 11;
            tmp.fontStyle = FontStyles.Bold;
            tmp.alignment = TextAlignmentOptions.Center;
        }

        var outlineGo = new GameObject("Outline");
        outlineGo.transform.SetParent(btnGo.transform, false);
        outlineGo.transform.SetAsFirstSibling();

        var outlineRect = outlineGo.AddComponent<RectTransform>();
        outlineRect.anchorMin = Vector2.zero;
        outlineRect.anchorMax = Vector2.one;
        outlineRect.offsetMin = new Vector2(-1, -1);
        outlineRect.offsetMax = new Vector2(1, 1);

        var outlineImg = outlineGo.AddComponent<Image>();
        outlineImg.color = new Color(
            glowColor.r, glowColor.g, glowColor.b, 0.4f);
        outlineImg.sprite = CreateRoundedSprite();
        outlineImg.type = Image.Type.Sliced;
    }

    private Sprite CreateRoundedSprite()
    {
        // Unity's default rounded UI sprite
        return Resources.Load<Sprite>("UI/Skin/UISprite");
    }
}