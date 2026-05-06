using System.Collections;
using UnityEngine;

public class AnimTest : MonoBehaviour
{

    public float startValue = 0;
    public float targetValue = 2;
    public float currentValue = 0;
    public Material material;
    public string shaderProperty = "CircleSize";
    public float speed = 1;
    Renderer renderer;

    private void Start() {
        StartCoroutine(Video());
    }

    private IEnumerator Video() {
        while (!Mathf.Approximately(currentValue, targetValue)) {
            currentValue = Mathf.MoveTowards(currentValue, targetValue, Time.deltaTime * speed);
            Debug.Log($"{material}.SetFloat({shaderProperty},{currentValue})");
            material.SetFloat(shaderProperty, currentValue);
            yield return null;
        }
    }

}
