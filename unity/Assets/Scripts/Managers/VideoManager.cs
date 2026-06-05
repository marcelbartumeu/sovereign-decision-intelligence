using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class VideoManager : MonoBehaviour {

    #region VARIABLES
    public List<Step> steps = new();

    private float totalTime = 0;
    private float currentGlobalTime = 0;
    private float currentStepTime = 0;

    private bool isPlaying = false;
    private int currentStepIndex;
    private Step currentStep;
    private Coroutine videoCoroutine;

    [SerializeField]
    private GameObject pauseUiObj;

    public static VideoManager instance;
    #endregion

    #region EVENTS
    private void Start() {
        Application.targetFrameRate = 60;
        Initialize();
    }

    private void Awake() {
        if (instance == null) instance = this;
    }

    private void Update() {
        HandleInput();
    }

    void OnEnable() {
        CoordManager.OnDataReady += StartVideo;
    }

    void OnDisable() {
        CoordManager.OnDataReady -= StartVideo;
    }

    private void OnDestroy() {
        if (videoCoroutine != null) {
            StopCoroutine(videoCoroutine);
        }
    }
    #endregion

    #region METHODS
    private void Initialize() {
        totalTime = GetTotalTime();
        UIManager.instance.SetMaxTime(totalTime);
    }

    public void StartVideo() {
        isPlaying = true;
        videoCoroutine = StartCoroutine(VideoRoutine());
    }

    private void ResetVideoState() {
        currentGlobalTime = 0;
        currentStepIndex = 0;
        currentStepTime = 0;
        currentStep = steps[currentStepIndex];
    }

    public float GetTotalTime() {
        float result = 0f;

        foreach (Step step in steps) {
            if (step.toShow)
                result += step.displayTime;
        }

        return result;
    }

    private void HandleInput() {
        if (Input.GetKeyDown(KeyCode.Space))
            Pause();
        if (Input.GetKeyDown(KeyCode.LeftArrow))
            PreviousStep();
        if (Input.GetKeyDown(KeyCode.RightArrow))
            NextStep();
        if (Input.GetKeyDown(KeyCode.R))
            Reset();
        if (Input.GetKeyDown(KeyCode.Escape))
            Application.Quit();
    }


    private IEnumerator VideoRoutine() {

        ResetVideoState();
        yield return null;
        DisplayCurrentStep();

        while (isPlaying) {

            if (currentStepTime >= currentStep.displayTime) {
                GoToNextStep();
            }

            currentStepTime += Time.deltaTime;
            UIManager.instance.UpdateSlider(currentGlobalTime + currentStepTime);
            yield return null;
        }
    }

    private void GoToNextStep() {
        currentStepIndex++;

        if (currentStepIndex >= steps.Count) {
            ResetToFirstStep();
            DisplayCurrentStep();
            return;
        }

        currentGlobalTime += currentStep.displayTime;
        PaintCoordManager.instance.StopAllPainting();

        if (!steps[currentStepIndex].cleanPrevious) {
            foreach (PaintType paint in currentStep.paints) {
                PaintCoordManager.instance.StartPainting(paint, true);
            }
        }
        else
            PaintCoordManager.instance.ClearAllPaintedObjects();

        currentStep = steps[currentStepIndex];
        currentStepTime = 0;

        DisplayCurrentStep();
    }

    public void NextStep() {
        if (currentStepIndex < steps.Count) {
            GoToNextStep();
        }
        else {
            ResetToFirstStep();
        }
    }

    private void ResetToFirstStep() {
        CleanAllPainting();
        ResetVideoState();
    }

    public void PreviousStep() {

        if (steps.Count == 0) return;

        CleanAllPainting();

        currentStepIndex = (currentStepIndex - 1 + steps.Count) % steps.Count;
        currentStep = steps[currentStepIndex];

        RecalculateGlobalTime();

        currentStepTime = 0;
        DisplayCurrentStep();
    }

    public void Pause() {
        if (Time.timeScale == 0) {
            pauseUiObj.SetActive(false);
            Time.timeScale = 1;

        }
        else {
            pauseUiObj.SetActive(true);
            Time.timeScale = 0;
        }
    }

    public void Reset() {
        if (videoCoroutine != null) {
            StopCoroutine(videoCoroutine);
            videoCoroutine = null;
        }

        CleanAllPainting();
        StartVideo();
    }

    private void CleanAllPainting() {
        PaintCoordManager.instance.StopAllPainting();
        PaintCoordManager.instance.ClearAllPaintedObjects();
    }

    private void RecalculateGlobalTime() {
        currentGlobalTime = 0;
        for (int i = 0; i < currentStepIndex; i++) {
            if (steps[i].toShow)
                currentGlobalTime += steps[i].displayTime;
        }
    }

    private void DisplayCurrentStep() {

        UpdateText();
        ImageManager.instance.HideImage();

        // Update base material
        if (currentStep.baseMaterial != null && ProjectorManager.instance.GetBaseMaterial() != currentStep.baseMaterial)
            ProjectorManager.instance.SetBaseMaterial(currentStep.baseMaterial);

        // Update layer marerial
        if (currentStep.isLayer)
            ProjectorManager.instance.SetLayerMaterials(currentStep.layerMaterial, currentStep.layerOpacity);
        else
            ProjectorManager.instance.DisableAllLayers();

        // Update sprite
        if (currentStep.sprite != null)
            ImageManager.instance.ChangeImage(currentStep.sprite);

        // Update animation
        AnimManager.instance.StopCurrentAnimation();
        if (currentStep.hasAnim)
            AnimManager.instance.PlayAnimation(currentStep.anim);

        // Update painting
        if (currentStep.isPaint) {
            foreach (PaintType paint in currentStep.paints) {
                PaintCoordManager.instance.StartPainting(paint, paint.isForced);
            }
        }
    }


    private void UpdateText() {
        string textLeft = " ";
        string textRight = " ";

        if (currentStep.isRightLeftText) {
            if (!string.IsNullOrEmpty(currentStep.textKey)) {
                textLeft = LanguageManager.instance.GetTextByKey(currentStep.textKey, "Cat");
                textRight = LanguageManager.instance.GetTextByKey(currentStep.textKey, "Eng");
            }
        }

        UIManager.instance.UpdateText(textLeft, textRight);
    }
    #endregion
}
