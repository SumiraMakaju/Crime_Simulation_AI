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
        bool isMoving = _nav != null
            ? _nav.velocity.magnitude > 0.3f
            : false;

        switch (_currentState)
        {
            case "fleeing":
                AnimateWalk(fleeSwingAngle, fleeSpeed, isMoving);
                break;
            case "laying_low":
                AnimateCrouch();
                break;
            case "committing":
                AnimateCommit();
                break;
            default:
                AnimateWalk(walkSwingAngle, walkSpeed, isMoving);
                break;
        }

        // Head always looks toward movement direction
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