using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

[Serializable]
public class PaintLine : PaintType {
    public bool showStartEndPoints;
    public GameObject startEndPointPrefab;
    public LineRenderer lineRendererPrefab;

    public override IEnumerator Paint(bool isForced) {
        int index = 0;

        if (dataToPaint == null || dataToPaint.data == null || dataToPaint.data.Count == 0) {
            Debug.LogWarning("No data to paint for PaintLine");
            yield break;
        }

        if (lineRendererPrefab == null) {
            Debug.LogWarning("LineRenderer is null");
            yield break;
        }

        float startTime = Time.time;
        float expectedTimePerPoint = speed;

        LineRenderer newLine = (LineRenderer)PaintCoordManager.instance.InstantiateObject(lineRendererPrefab, Vector3.zero, Quaternion.identity);

        ConfigureLineRenderer(newLine);


        foreach (Data data in dataToPaint.data) {
            if (showStartEndPoints && (index == 0 || index == dataToPaint.data.Count - 1))
                PaintStartEndPosition(data.coord, color);

            AddPointToLine(data.coord, newLine, ref index);

            if (!isForced) {
                float elapsedTime = Time.time - startTime;
                float expectedElapsedTime = expectedTimePerPoint * newLine.positionCount;

                // Compensate for any timing errors
                float compensation = expectedElapsedTime - elapsedTime;
                yield return new WaitForSeconds(Mathf.Max(0f, expectedTimePerPoint + compensation));
            }
        }
    }

    private void ConfigureLineRenderer(LineRenderer newLine) {
        newLine.positionCount = 0;
        newLine.startWidth = size;
        newLine.endWidth = size;

        newLine.colorGradient = PaintCoordManager.instance.CreateColorGradient(color);
        newLine.sortingOrder = sortingOrder;
    }

    private void AddPointToLine(Vector3 coord, LineRenderer line, ref int index) {
        if (line == null)
            return;
        line.positionCount = index + 1;
        line.SetPosition(index, coord);
        index++;
    }

    private void PaintStartEndPosition(Vector3 coord, Color color) {
        GameObject instance = (GameObject)PaintCoordManager.instance.InstantiateObject(startEndPointPrefab, coord, Quaternion.Euler(90, 0, 0));
        instance.GetComponent<Image>().color = color;
    }
}
