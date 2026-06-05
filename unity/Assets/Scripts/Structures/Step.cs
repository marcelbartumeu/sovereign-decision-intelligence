using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

[CreateAssetMenu(fileName = "Step", menuName = "Scriptable/Steps")]
[Serializable]
public class Step : ScriptableObject {
    [HideInInspector]
    public bool showStepEditor;

    public bool toShow;

    public bool cleanPrevious = true;

    public bool isLayer;
    public Material baseMaterial;
    public List<Material> layerMaterial;
    [Range(0f, 1f)]
    public float layerOpacity;

    public bool isPaint;
    [SerializeReference]
    public List<PaintType> paints = new();

    public bool isRightLeftText;
    public string textKey;

    public Sprite sprite = null;

    public bool hasAnim;
    public Anim anim;

    public float displayTime;

    public void GetTotalDrawingTime() {

        foreach (PaintType paint in paints) {
            float seconds = 0;

            if (paint.dataToPaint == null || paint.dataToPaint.data.Count == 0) {
                paint.drawingTime = seconds.ToString();
                continue;
            }

            seconds = paint.speed * paint.dataToPaint.data.Count;
            paint.drawingTime = seconds.ToString();
        }
    }
}

[Serializable]
public class Anim {
    public Material material;
    public float startValue;
    public float targetValue;
    public float speed;
    public string shaderProperty;
    public bool isLoop;
    public bool isSnow;
}
