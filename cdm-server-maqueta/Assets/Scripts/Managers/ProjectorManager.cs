using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.Universal;

public class ProjectorManager : MonoBehaviour{

    [SerializeField]
    private DecalProjector baseProjector;
    [SerializeField]
    private List<DecalProjector> layerProjectors;

    public static ProjectorManager instance;

    private void Awake() {
        if(instance == null) instance = this;
    }

    public void SetBaseMaterial(Material material) {
        baseProjector.material = material;
    }

    public void SetLayerMaterials(List<Material> material, float opacity) {

        for(int i = 0; i < layerProjectors.Count; i++) {
            DecalProjector projector = layerProjectors[i];
            if (projector == null) continue;

            if (i < material.Count && material[i] != null) {
                projector.material = material[i];
                projector.gameObject.SetActive(true);
                projector.fadeFactor = (i == material.Count - 1) ? opacity : 1f;
            } else 
                projector.gameObject.SetActive(false);
        }
    }

    public void DisableAllLayers() {
        foreach (DecalProjector proj in layerProjectors) 
            proj.gameObject.SetActive(false);
    }

    public Material GetBaseMaterial() {
        return baseProjector.material;
    }
}
