using UnityEngine;
using TMPro;

public class AgentBadge : MonoBehaviour
{
    private TextMeshPro _tmp;
    private Camera _cam;
    private Transform _follow;
    private float _heightOffset = 1.5f;


    public static AgentBadge Create(Transform followTarget, float height = 1.5f)
    {
        var go = new GameObject("AgentBadge");
        var badge = go.AddComponent<AgentBadge>();
        badge._follow = followTarget;
        badge._heightOffset = height;
        badge.Init();
        return badge;
    }

    private void Init()
    {
        _cam = Camera.main;

        _tmp = gameObject.AddComponent<TextMeshPro>();
        _tmp.fontSize = 2f;
        _tmp.alignment = TextAlignmentOptions.Center;
        _tmp.fontStyle = FontStyles.Bold;
        _tmp.text = "";

        // Render above everything
        _tmp.sortingOrder = 10;

        transform.localScale = Vector3.one * 0.5f;
    }
    void LateUpdate()
    {
        if (_follow == null) return;

        // Follow agent position
        transform.position = _follow.position + Vector3.up * _heightOffset;

        // Billboard  always face camera
        if (_cam != null)
            transform.forward = _cam.transform.forward;
    }

    public void SetState(string agentType, string state)
    {
        if (_tmp == null) return;

        switch (agentType)
        {
            case "criminal":
                switch (state)
                {
                    case "committing":
                        _tmp.text = "CRIME IN PROGRESS";
                        _tmp.color = new Color(1f, 0.2f, 0.2f);
                        break;
                    case "fleeing":
                        _tmp.text = "FLEEING";
                        _tmp.color = new Color(1f, 0.6f, 0.1f);
                        break;
                    case "laying_low":
                        _tmp.text = "HIDING";
                        _tmp.color = new Color(0.5f, 0.5f, 0.5f);
                        break;
                    default:
                        _tmp.text = "";
                        break;
                }
                break;

            case "police":
                switch (state)
                {
                    case "responding":
                        _tmp.text = "RESPONDING";
                        _tmp.color = new Color(0.2f, 0.6f, 1f);
                        break;
                    default:
                        _tmp.text = "";
                        break;
                }
                break;

            case "civilian":
                switch (state)
                {
                    case "fleeing":
                        _tmp.text = "PANIC";
                        _tmp.color = new Color(1f, 0.8f, 0.2f);
                        break;
                    default:
                        _tmp.text = "";
                        break;
                }
                break;

            default:
                _tmp.text = "";
                break;
        }
    }

    public void Hide() => gameObject.SetActive(false);
    public void Show() => gameObject.SetActive(true);

    void OnDestroy()
    {
        if (gameObject != null)
            Destroy(gameObject);
    }
}