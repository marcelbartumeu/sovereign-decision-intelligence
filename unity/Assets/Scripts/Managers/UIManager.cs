using UnityEngine;
using UnityEngine.UI;
using TMPro;


public class UIManager : MonoBehaviour{
    [SerializeField]
    private Slider timeSlider;

    [SerializeField]
    private TextMeshProUGUI leftSite;
    [SerializeField]
    private TextMeshProUGUI rightSide;

    public static UIManager instance;

    private void Awake() {
        if (instance == null) instance = this;   
    }

    public void SetMaxTime(float time) {
        timeSlider.maxValue = time;
    }

    public void UpdateSlider(float value) {
        timeSlider.value = value;
    }

    public void UpdateText(string textLeft, string textRight) { 
        leftSite.text = textLeft;
        rightSide.text = textRight;
    }
}
