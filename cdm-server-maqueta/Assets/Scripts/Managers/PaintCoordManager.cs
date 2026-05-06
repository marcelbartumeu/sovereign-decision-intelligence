using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class PaintCoordManager : MonoBehaviour{

    [SerializeField]
    private Transform paintContainer;
    [SerializeField]
    private Image paintImage;
    [SerializeField]
    private GameObject blinkPrefab;

    public Image PaintImage => paintImage;
    public GameObject BlinkPrefab => blinkPrefab;


    public static PaintCoordManager instance;

    private List<Coroutine> activeCoroutines = new();

    private void Awake() {
        if (instance == null) instance = this;
    }

    public void StartPainting(PaintType paint, bool isForced) {
        activeCoroutines.Add(StartCoroutine(paint.Paint(isForced)));
    }

    public Gradient CreateColorGradient(UnityEngine.Color color) {
        Gradient gradient = new();

        // Set color keys (same color at start and end)
        GradientColorKey[] colorKeys = new GradientColorKey[2] {
            new (color, 0), // Start color
            new (color, 1), // End color
        };

        // Set alpha keys (fully opaque)
        GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2] {
            new (1, 0), // Start alpha
            new (1, 1), // End alpha
        };
     
        // Assign the keys to the gradient
        gradient.SetKeys(colorKeys, alphaKeys);
        return gradient;
    }

    public Object InstantiateObject(Object obj, Vector3 pos,Quaternion quat) {
        return Instantiate(obj, pos, quat, paintContainer);
    }

    public void StopAllPainting() {
        foreach(Coroutine coroutine in activeCoroutines) {
            if (coroutine != null) StopCoroutine(coroutine);
        }
        activeCoroutines.Clear();
    }

    public void ClearAllPaintedObjects() {
        StopAllPainting();

        if (paintContainer == null) return;

        // Get all the childrens of the container
        int childCount = paintContainer.childCount;
        // Iterates them
        for (int i = childCount - 1; i >= 0; i--) {
            Transform child = paintContainer.GetChild(i);
            if (child != null)
                Destroy(child.gameObject);
        }
    }
}
