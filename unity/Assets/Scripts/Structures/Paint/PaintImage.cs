using System;
using UnityEngine;
using UnityEngine.UI;

[Serializable]
public class ImageManager : MonoBehaviour  {

    public Image img;

    public static ImageManager instance;

    private void Awake() {
        if(instance == null) instance = this;
    }

    public void ChangeImage(Sprite sprite) {
        img.sprite = sprite;
        img.gameObject.SetActive(true);
    }

    public void HideImage() {
        img.gameObject.SetActive(false);
    }
}
