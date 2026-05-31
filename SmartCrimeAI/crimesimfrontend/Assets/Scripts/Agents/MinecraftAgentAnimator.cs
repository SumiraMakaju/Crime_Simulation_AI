using UnityEngine;
using UnityEngine.AI;

public class MinecraftAgentAnimator : MonoBehaviour
{
    [Header("Limb References — assign in Inspector after prefab creation")]
    public Transform armL;
    public Transform armR;
    public Transform legL;
    public Transform legR;
    public Transform head;
    public Transform body;

    [Header("Animation Settings")]
    public float walkSwingAngle = 35f;   // max degrees arms/legs swing while walking
    public float walkSpeed = 8f;    // how fast the swing cycles
    public float fleeSwingAngle = 50f;   // exaggerated swing when fleeing
    public float fleeSpeed = 14f;
    public float idleBobAmount = 0.03f; // subtle up-down while idle
    public float idleBobSpeed = 1.5f;
    public float headLookSpeed = 3f;    // how fast head turns to face movement dir

 
    private NavMeshAgent _nav;
    private float _swingTime;
    private Vector3 _armLDefaultRot;
    private Vector3 _armRDefaultRot;
    private Vector3 _legLDefaultRot;
    private Vector3 _legRDefaultRot;
    private Vector3 _bodyDefaultPos;
    private string _currentState = "walking";
 
    void Awake()
    {
        _nav = GetComponent<NavMeshAgent>();

        // Store default local rotations so we can lerp back to them
        if (armL) _armLDefaultRot = armL.localEulerAngles;
        if (armR) _armRDefaultRot = armR.localEulerAngles;
        if (legL) _legLDefaultRot = legL.localEulerAngles;
        if (legR) _legRDefaultRot = legR.localEulerAngles;
        if (body) _bodyDefaultPos = body.localPosition;
    }


    void Update()
    {
        bool isMoving = _nav != null && _nav.velocity.magnitude > 0.5f;

        switch (_currentState)
        {
            case "fleeing":
                AnimateFlee(isMoving);
                break;
            case "laying_low":
                AnimateCrouch();
                break;
            case "committing":
                AnimateCommit();
                break;
            case "handcuffed":
                AnimateHandcuffed();
                break;
            default:
                AnimateWalk(walkSwingAngle, walkSpeed, isMoving);
                break;
        }

        // Head faces movement direction
        if (_nav != null && _nav.velocity.magnitude > 0.3f && head != null)
        {
            Vector3 flatVel = new Vector3(_nav.velocity.x, 0, _nav.velocity.z);
            if (flatVel != Vector3.zero)
            {
                Quaternion targetRot = Quaternion.LookRotation(flatVel);
                head.rotation = Quaternion.Slerp(
                    head.rotation, targetRot, Time.deltaTime * headLookSpeed);
            }
        }
    }

    // ── Flee: arms raised above head, fast leg movement ──────────────────
    private void AnimateFlee(bool isMoving)
    {
        _swingTime += Time.deltaTime * fleeSpeed;
        float swing = Mathf.Sin(_swingTime) * fleeSwingAngle;

        // Arms raised high (panic)
        if (armL) armL.localEulerAngles = new Vector3(-140f, 0, -15f);
        if (armR) armR.localEulerAngles = new Vector3(-140f, 0, 15f);

        // Legs run fast
        if (legL) legL.localEulerAngles = new Vector3(-swing, 0, 0);
        if (legR) legR.localEulerAngles = new Vector3(swing, 0, 0);

        // Body leans forward
        if (body) body.localEulerAngles = Vector3.Lerp(
            body.localEulerAngles, new Vector3(20f, 0, 0), Time.deltaTime * 5f);
    }

    // ── Handcuffed: both arms stretched forward, body bent ───────────────
    private void AnimateHandcuffed()
    {
        // Arms stretched straight forward (wrists together)
        if (armL) armL.localEulerAngles = Vector3.Lerp(
            armL.localEulerAngles, new Vector3(-80f, 0, 15f), Time.deltaTime * 8f);
        if (armR) armR.localEulerAngles = Vector3.Lerp(
            armR.localEulerAngles, new Vector3(-80f, 0, -15f), Time.deltaTime * 8f);

        // Legs together, slightly bent
        if (legL) legL.localEulerAngles = Vector3.Lerp(
            legL.localEulerAngles, new Vector3(15f, 0, 5f), Time.deltaTime * 8f);
        if (legR) legR.localEulerAngles = Vector3.Lerp(
            legR.localEulerAngles, new Vector3(15f, 0, -5f), Time.deltaTime * 8f);

        // Body bent forward submissively
        if (body) body.localEulerAngles = Vector3.Lerp(
            body.localEulerAngles, new Vector3(30f, 0, 0), Time.deltaTime * 8f);

        // Head bowed down
        if (head) head.localEulerAngles = Vector3.Lerp(
            head.localEulerAngles, new Vector3(20f, 0, 0), Time.deltaTime * 8f);
    }

    private void AnimateWalk(float swingAngle, float speed, bool isMoving)
    {
        if (isMoving)
        {
            _swingTime += Time.deltaTime * speed;

            float swing = Mathf.Sin(_swingTime) * swingAngle;

            // Arms swing opposite to legs (like real walking)
            if (armL) armL.localEulerAngles = new Vector3(swing, 0, 0);
            if (armR) armR.localEulerAngles = new Vector3(-swing, 0, 0);
            if (legL) legL.localEulerAngles = new Vector3(-swing, 0, 0);
            if (legR) legR.localEulerAngles = new Vector3(swing, 0, 0);
        }
        else
        {
            // Idle: subtle body bob, limbs return to default
            _swingTime += Time.deltaTime * idleBobSpeed;

            if (armL) armL.localEulerAngles = Vector3.Lerp(
                armL.localEulerAngles, _armLDefaultRot, Time.deltaTime * 5f);
            if (armR) armR.localEulerAngles = Vector3.Lerp(
                armR.localEulerAngles, _armRDefaultRot, Time.deltaTime * 5f);
            if (legL) legL.localEulerAngles = Vector3.Lerp(
                legL.localEulerAngles, _legLDefaultRot, Time.deltaTime * 5f);
            if (legR) legR.localEulerAngles = Vector3.Lerp(
                legR.localEulerAngles, _legRDefaultRot, Time.deltaTime * 5f);

            // Subtle vertical bob on body
            if (body)
            {
                float bob = Mathf.Sin(_swingTime) * idleBobAmount;
                body.localPosition = _bodyDefaultPos + new Vector3(0, bob, 0);
            }
        }
    }
 
    private void AnimateCrouch()
    {
        // Crouch: body lower, legs bent outward
        if (body) body.localPosition = Vector3.Lerp(
            body.localPosition,
            _bodyDefaultPos + new Vector3(0, -0.25f, 0),
            Time.deltaTime * 4f);

        if (legL) legL.localEulerAngles = Vector3.Lerp(
            legL.localEulerAngles, new Vector3(30, 0, 10), Time.deltaTime * 4f);
        if (legR) legR.localEulerAngles = Vector3.Lerp(
            legR.localEulerAngles, new Vector3(30, 0, -10), Time.deltaTime * 4f);
        if (armL) armL.localEulerAngles = Vector3.Lerp(
            armL.localEulerAngles, new Vector3(0, 0, -20), Time.deltaTime * 4f);
        if (armR) armR.localEulerAngles = Vector3.Lerp(
            armR.localEulerAngles, new Vector3(0, 0, 20), Time.deltaTime * 4f);
    }
 
    private void AnimateCommit()
    {
        // Committing crime: right arm raised and swinging down repeatedly
        _swingTime += Time.deltaTime * 6f;
        float swing = (Mathf.Sin(_swingTime) * 0.5f + 0.5f) * -70f;  // 0 to -70 degrees

        if (armR) armR.localEulerAngles = new Vector3(swing, 0, 0);
        if (armL) armL.localEulerAngles = new Vector3(-20, 0, 0);  // slightly back
    }
 
    public void SetState(string state)
    {
        _currentState = state;
    }
}