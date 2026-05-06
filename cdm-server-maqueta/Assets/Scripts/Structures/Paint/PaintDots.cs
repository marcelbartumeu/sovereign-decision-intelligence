using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

[Serializable]
public class PaintDots : PaintType {

    public Sprite sprite;

    public override IEnumerator Paint(bool isForced) {
        float startTime = Time.time;
        float expectedTimePerPoint = speed;
        float index = 0;

        if (dataToPaint == null || dataToPaint.data == null || dataToPaint.data.Count == 0) {
            Debug.LogWarning("No data to paint for PaintDots");
            yield break;
        }

        Image img = PaintCoordManager.instance.PaintImage;
        if (img == null) {
            Debug.LogWarning("Paint image is null");
            yield break;
        }

        foreach (Data data in dataToPaint.data) {

            ConfigureDotAppearance(img, data);

            index++;

            if (!isForced) {
                float elapsedTime = Time.time - startTime;
                float expectedElapsedTime = expectedTimePerPoint * index;

                // Compensate for any timing errors
                float compensation = expectedElapsedTime - elapsedTime;
                yield return new WaitForSeconds(Mathf.Max(0f, expectedTimePerPoint + compensation));

            }
        }
    }

    private void ConfigureDotAppearance(Image image, Data dataPoint) {
        if (dataPoint.GetField(Types.Color, out Color customColor))
            image.color = customColor;
        else
            image.color = color;

        if (dataPoint.GetField(Types.Size, out float customSize))
            image.rectTransform.sizeDelta = new Vector2(customSize, customSize);
        else
            image.rectTransform.sizeDelta = new Vector2(size, size);

        image.sprite = sprite;

        if (!ApplyAppearanceException(dataPoint, customColor, customSize))
            PaintCoordManager.instance.InstantiateObject(image, dataPoint.coord, Quaternion.Euler(90, 0, 0));
    }

    private bool ApplyAppearanceException(Data dataPoint, Color customColor, float customSize) {

        if (dataPoint.GetField(Types.Name, out string customName) && customName == "Pic de Coma Pedrosa") {

            GameObject instance = (GameObject)PaintCoordManager.instance.InstantiateObject(PaintCoordManager.instance.BlinkPrefab, dataPoint.coord, Quaternion.Euler(90, 0, 0));

            Image img = instance.GetComponent<Image>();
            img.color = customColor;
            img.sprite = sprite;
            img.GetComponent<RectTransform>().sizeDelta = new Vector2(customSize, customSize);
            return true;
        }

        return false;
    }
}
