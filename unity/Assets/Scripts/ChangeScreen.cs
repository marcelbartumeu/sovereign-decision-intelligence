using UnityEngine;

public class ActivateAllDisplays : MonoBehaviour {
    void Start() {
        // Display.displays[0] is the primary, default display and is always ON, so start at index 1.
        // Check if additional displays are available and activate each.

        for (int i = 1; i < Display.displays.Length; i++) {
            Display.displays[i].Activate();
        }
        Cursor.visible = false;

        float scaleFactor = 0.965f;
        Camera.main.rect = new Rect(0, 0, 1, scaleFactor);
    }
}