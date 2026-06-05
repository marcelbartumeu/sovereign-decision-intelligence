using UnityEngine;

[CreateAssetMenu(fileName = "NewMapRefs", menuName = "Scriptable/MapRefs")]
public class CoordinatesRefs : ScriptableObject{

    [Header("References World")]
    [SerializeField]
    private Vector3 topLeft_world;
    public Vector3 TopLeft_world { get { return topLeft_world; } }
    [SerializeField]
    private Vector3 topRight_world;
    public Vector3 TopRight_world { get { return topRight_world; } }
    [SerializeField]
    private Vector3 botLeft_world;
    public Vector3 BotLeft_world { get { return botLeft_world; } }
    [SerializeField]
    private Vector3 botRight_world;
    public Vector3 BotRight_world { get { return botRight_world; } }

    [Header("References IRL")]
    [SerializeField]
    private Vector2 topLeft_irl;
    public Vector2 TopLeft_irl { get { return topLeft_irl; } set { topLeft_irl = value; } }
    [SerializeField]
    private Vector2 topRight_irl;
    public Vector2 TopRight_irl { get { return topRight_irl; } set { topRight_irl = value; } }
    [SerializeField]
    private Vector2 botLeft_irl;
    public Vector2 BotLeft_irl { get { return botLeft_irl; } set { botLeft_irl = value; } }
    [SerializeField]
    private Vector2 botRight_irl;
    public Vector2 BotRight_irl { get { return botRight_irl; } set { botRight_irl = value; } }
}
