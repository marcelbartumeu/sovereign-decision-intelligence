using UnityEngine;

public class Spawn : MonoBehaviour
{
    // Start is called before the first frame update

    public GameObject prefab;

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Space)) {
            Instantiate(prefab, new Vector3(0,0,0), Quaternion.identity);
        }
    }
}
