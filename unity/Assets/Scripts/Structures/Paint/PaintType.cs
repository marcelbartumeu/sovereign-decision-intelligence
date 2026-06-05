using System;
using System.Collections;
using UnityEngine;

[Serializable]
public abstract class PaintType {

    public bool showPaintEditor;
    public string drawingTime;

    public DataList dataToPaint;

    public bool isForced;

    [Range(0.016f, 0.5f)]
    public float speed = 0.02f;
    public float size = 0.5f;

    public Color color;

    public int sortingOrder = 1;

    public abstract IEnumerator Paint(bool isForced);
}
