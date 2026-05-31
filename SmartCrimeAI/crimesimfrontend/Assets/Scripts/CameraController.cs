// CameraController.cs
// Smooth pan, zoom, and orbit camera for the SmartCrimeAI simulation.
// Attach to Main Camera.

using UnityEngine;

public class CameraController : MonoBehaviour
{
    [Header("Pan Settings")]
    public float panSpeed = 20f;
    public float panSmoothing = 8f;
    public float edgePanThreshold = 20f;   // pixels from screen edge
    public bool useEdgePanning = true;

    [Header("Zoom Settings")]
    public float zoomSpeed = 5f;
    public float zoomSmoothing = 8f;
    public float minZoom = 20f;
    public float maxZoom = 100f;

    [Header("Orbit Settings")]
    public float orbitSpeed = 100f;
    public float minPitch = 20f;   // degrees — how low you can go
    public float maxPitch = 89f;   // degrees — straight down

    [Header("City Bounds — keeps camera over the grid")]
    public float boundMinX = -10f;
    public float boundMaxX = 70f;
    public float boundMinZ = -10f;
    public float boundMaxZ = 70f;

    [Header("Starting Position")]
    public Vector3 startPosition = new Vector3(30f, 805f, -45f);
    public Vector3 startRotation = new Vector3(45f, 0f, 0f);

    //   Internal  
    private Vector3 _targetPosition;
    private float _targetZoom;
    private float _currentYaw;
    private float _currentPitch;
    private bool _isOrbiting;
    private Vector3 _lastMousePos;
    private Vector3 _orbitTarget;

    
    void Start()
    {
        transform.position = startPosition;
        transform.eulerAngles = startRotation;

        _targetPosition = startPosition;
        _targetZoom = startPosition.y;
        _currentYaw = startRotation.y;
        _currentPitch = startRotation.x;
        _orbitTarget = new Vector3(30f, 0f, 30f); // city center
    }

    void Update()
    {
        HandleZoom();
        HandlePan();
        HandleOrbit();
        HandleKeyboardShortcuts();
        ApplyMovement();
    }

    private void HandleZoom()
    {
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 0.01f)
            _targetZoom = Mathf.Clamp(_targetZoom - scroll * zoomSpeed * 10f,
                                      minZoom, maxZoom);
    }
    private void HandlePan()
    {
        // Skip pan while orbiting
        if (_isOrbiting) return;

        Vector3 panDelta = Vector3.zero;

        //  WASD / Arrow keys 
        if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow))
            panDelta += GetForwardFlat() * panSpeed * Time.deltaTime;
        if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow))
            panDelta -= GetForwardFlat() * panSpeed * Time.deltaTime;
        if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow))
            panDelta -= transform.right * panSpeed * Time.deltaTime;
        if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow))
            panDelta += transform.right * panSpeed * Time.deltaTime;

        //  Middle mouse button drag 
        if (Input.GetMouseButtonDown(2))
            _lastMousePos = Input.mousePosition;

        if (Input.GetMouseButton(2))
        {
            Vector3 delta = Input.mousePosition - _lastMousePos;
            _lastMousePos = Input.mousePosition;

            panDelta -= transform.right * delta.x * 0.05f;
            panDelta -= GetForwardFlat() * delta.y * 0.05f;
        }

        //  Edge panning 
        if (useEdgePanning && !Application.isEditor)
        {
            Vector3 mouse = Input.mousePosition;
            float w = Screen.width;
            float h = Screen.height;

            if (mouse.x < edgePanThreshold)
                panDelta -= transform.right * panSpeed * Time.deltaTime;
            if (mouse.x > w - edgePanThreshold)
                panDelta += transform.right * panSpeed * Time.deltaTime;
            if (mouse.y < edgePanThreshold)
                panDelta -= GetForwardFlat() * panSpeed * Time.deltaTime;
            if (mouse.y > h - edgePanThreshold)
                panDelta += GetForwardFlat() * panSpeed * Time.deltaTime;
        }

        // Apply pan — keep Y the same, clamp to bounds
        _targetPosition += panDelta;
        _targetPosition.x = Mathf.Clamp(_targetPosition.x, boundMinX, boundMaxX);
        _targetPosition.z = Mathf.Clamp(_targetPosition.z, boundMinZ, boundMaxZ);
    }

    private void HandleOrbit()
    {
        // Right mouse button = orbit
        if (Input.GetMouseButtonDown(1))
        {
            _isOrbiting = true;
            _lastMousePos = Input.mousePosition;
        }

        if (Input.GetMouseButtonUp(1))
            _isOrbiting = false;

        if (_isOrbiting && Input.GetMouseButton(1))
        {
            Vector3 delta = Input.mousePosition - _lastMousePos;
            _lastMousePos = Input.mousePosition;

            _currentYaw += delta.x * orbitSpeed * Time.deltaTime;
            _currentPitch -= delta.y * orbitSpeed * Time.deltaTime;
            _currentPitch = Mathf.Clamp(_currentPitch, minPitch, maxPitch);
        }
    }

 
    private void HandleKeyboardShortcuts()
    {
        // R = reset camera to default view
        if (Input.GetKeyDown(KeyCode.R))
        {
            _targetPosition = startPosition;
            _targetZoom = startPosition.y;
            _currentYaw = startRotation.y;
            _currentPitch = startRotation.x;
        }

        // F = focus on city center
        if (Input.GetKeyDown(KeyCode.F))
        {
            _targetPosition = new Vector3(30f, _targetZoom, 30f);
        }

        // 1 = top-down view
        if (Input.GetKeyDown(KeyCode.Alpha1))
        {
            _currentPitch = 89f;
            _currentYaw = 0f;
        }

        // 2 = angled view (default)
        if (Input.GetKeyDown(KeyCode.Alpha2))
        {
            _currentPitch = 70f;
            _currentYaw = 0f;
        }

        // 3 = low angle view
        if (Input.GetKeyDown(KeyCode.Alpha3))
        {
            _currentPitch = 30f;
        }

        // Speed boost with Shift
        if (Input.GetKey(KeyCode.LeftShift))
        {
            panSpeed = 40f;
            zoomSpeed = 10f;
        }
        else
        {
            panSpeed = 20f;
            zoomSpeed = 5f;
        }
    }

    private void ApplyMovement()
    {
        // Smoothly interpolate position and zoom
        Vector3 desiredPos = new Vector3(
            _targetPosition.x,
            _targetZoom,
            _targetPosition.z);

        transform.position = Vector3.Lerp(
            transform.position, desiredPos, Time.deltaTime * panSmoothing);

        // Apply orbit rotation
        Quaternion targetRot = Quaternion.Euler(_currentPitch, _currentYaw, 0f);
        transform.rotation = Quaternion.Slerp(
            transform.rotation, targetRot, Time.deltaTime * panSmoothing);
    }

    // Returns camera forward projected flat on XZ plane (ignores Y)
    private Vector3 GetForwardFlat()
    {
        Vector3 forward = transform.forward;
        forward.y = 0f;
        return forward.normalized;
    }

    /// <summary>Called by SimulationManager to focus camera on an agent</summary>
    public void FocusOn(Vector3 worldPos)
    {
        _targetPosition = new Vector3(worldPos.x, _targetPosition.y, worldPos.z);
    }
}