using System.Collections;
using UnityEngine;
using UnityEngine.Rendering.Universal;

public class AnimManager : MonoBehaviour{

    private Coroutine coroutine;
    private float currentValue = 0;

    [SerializeField]
    private DecalProjector snowProjector;
    [SerializeField]
    private Animator animator;
    private Anim currentAnimation = null;

    public static AnimManager instance;

    private void Awake() {
        if(instance == null) instance = this;
    }

    public void PlayAnimation(Anim animation) {
        if (animation.isSnow) {
            PlaySnowAnimation(animation);
        } else {
            PlayShaderAnimation(animation);
        }
    }

    private IEnumerator Animation() {

        while (!Mathf.Approximately(currentValue, currentAnimation.targetValue)) {
            currentValue = Mathf.MoveTowards(currentValue, currentAnimation.targetValue, Time.deltaTime * currentAnimation.speed);
            currentAnimation.material.SetFloat(currentAnimation.shaderProperty, currentValue);
            yield return null;
        }

        ForceEndAnimation();

        if (currentAnimation.isLoop) {
            currentValue = currentAnimation.startValue;
            coroutine = StartCoroutine(Animation());
        }
    }

    private void PlaySnowAnimation(Anim animation) {
        snowProjector.gameObject.SetActive(true);
        animator.SetTrigger(animation.shaderProperty);
    }

    private void PlayShaderAnimation(Anim animation) {
        currentValue = animation.startValue;
        animation.material.SetFloat(animation.shaderProperty, animation.startValue);
        
        currentAnimation = animation;
        coroutine = StartCoroutine(Animation());
    }

    public void StopCurrentAnimation() {
        if (coroutine != null) {
            StopCoroutine(coroutine);
            coroutine = null;
        }

        if (currentAnimation != null) {
            ForceEndAnimation();
            currentAnimation = null;
        }
    }

    public void ForceEndAnimation() {
        if (currentAnimation?.material != null) {
            currentAnimation.material.SetFloat(currentAnimation.shaderProperty, currentAnimation.targetValue);
        }
    }
}
