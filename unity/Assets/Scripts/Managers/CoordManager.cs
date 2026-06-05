using System;
using System.Xml;
using UnityEngine;

public class CoordManager : MonoBehaviour {

    public static CoordManager instance;

    [SerializeField]
    private CoordinatesRefs coordRefs;
    //private Vector2 currentCoor;

    private double longTotIrl;
    private double latTotIrl;
    private float longTotWorld;
    private float latTotWorld;

    public static event Action OnLoadData;
    public static event Action OnDataReady;


    [SerializeField]
    private LayerMask mapLayer;

    private void Awake() {
        if (instance == null) instance = this;
    }

    private void Start() {
        latTotIrl = GetTotalLatIrl();
        longTotIrl = GetTotalLongIrl();
        latTotWorld = GetTotalLatWorld();
        longTotWorld = GetTotalLongWorld();

        OnLoadData?.Invoke();
        OnDataReady?.Invoke();
    }

    /// <summary>
    /// Open and load the XML Document and returns it
    /// </summary>
    /// <returns></returns>
    public XmlDocument OpenXmlDoc(TextAsset asset) {
        // If fail, return
        if (asset == null) {
            Debug.Log("Unable to open <b>Coords XML</b>");
            return null;
        }

        // Create a xmlDoc
        XmlDocument xmlDocument = new();

        try {
            // Load the xml content
            xmlDocument.LoadXml(asset.text);
        }
        catch (XmlException e) {
            Debug.Log("Error Loading the XML: " + e);
        }

        return xmlDocument;
    }


    #region GetCoordPos
    /// <summary>
    /// Calculate the total Long of the map (Physic) or tile (Mabpox)
    /// </summary>
    /// <returns>total long</returns>
    private double GetTotalLongIrl() {
        return coordRefs.TopRight_irl.y - coordRefs.TopLeft_irl.y;
    }

    /// <summary>
    /// Calculate the total Lat of the map (Physic) or tile (Mabpox)
    /// </summary>
    /// <returns>total lat</returns>
    private double GetTotalLatIrl() {
        return coordRefs.TopLeft_irl.x - coordRefs.BotLeft_irl.x;
    }

    /// <summary>
    /// Calculate the total Long of the map (Physic) or tile (Mabpox)
    /// </summary>
    /// <returns>total long</returns>
    private float GetTotalLongWorld() {
        return coordRefs.BotRight_world.x - coordRefs.BotLeft_world.x;
    }

    /// <summary>
    /// Calculate the total Lat of the map (Physic) or tile (Mabpox)
    /// </summary>
    /// <returns>total lat</returns>
    private float GetTotalLatWorld() {
        return coordRefs.TopLeft_world.z - coordRefs.BotLeft_world.z;
    }

    /// <summary>
    /// Calculate the X position of the current coord respective to irl
    /// 
    /// Exemple: - - - - -        If "-" is the map and "." the given longitud. If 
    ///          - . - - -        we know the irl and world positions of the corners, 
    ///          - - - - -        we want to find its relative position in the X
    ///     corner - - - -        axis in order to find its X world position.
    ///     East x(-)ooooo West   We want to know the x distance.
    ///     
    /// </summary>
    /// <returns>X relative Position</returns>
    private double GetXRelativePos(Vector2 currentCoor) {
        // currentCoord.x = Lat, currentCoord.y = Lon 
        double result = currentCoor.y - coordRefs.BotLeft_irl.y;
        return result / longTotIrl;
    }

    /// <summary>
    /// Calculate the Y position of the current coord respective to irl
    ///                    North
    /// Exemple: - - - - -   o    If "-" is the map and "." the given latitude. 
    ///          - . - - -  (-)   If we know the irl and world positions, we  
    ///          - - - - -   x    want to find its relative position in the Y
    ///     corner - - - -   x    axis in order to find its Y world position.
    ///                    South  We want to know the x distance.
    /// </summary>
    /// <returns>Y relative Position</returns>
    private double GetYRelativePos(Vector2 currentCoor) {
        // currentCoord.x = Lat, currentCoord.y = Lon 
        double result = currentCoor.x - coordRefs.BotLeft_irl.x;
        return result / latTotIrl;
    }

    /// <summary>
    /// Calculates the World position X Z
    /// </summary>
    /// <param name="lat"></param>
    /// <param name="lon"></param>
    /// <returns>Unity position</returns>
    public Vector3 CalculateXYPosition(float lat, float lon) {

        Vector2 currentCoor = new(lat, lon);

        // Calculate x and y relative positions
        double xRelPos = GetXRelativePos(currentCoor);
        double yRelPos = GetYRelativePos(currentCoor);

        Vector3 result = Vector3.zero;

        // Calculate world position with the relative one
        result.x = coordRefs.BotLeft_world.x + (float)xRelPos * longTotWorld;
        result.z = coordRefs.BotLeft_world.z + (float)yRelPos * latTotWorld;
        result.y = GetAltitude(result);

        return result;
    }

    /// <summary>
    /// Returns coord Y position with a RayCast
    /// </summary>
    /// <param name="x"></param>
    /// <param name="z"></param>
    /// <returns>height of colision</returns>
    public float GetAltitude(Vector3 res) {

        RaycastHit hit;
        // Raycast the map from a height of 50 with a max distance of 70 units
        if (!Physics.Raycast(new Vector3(res.x, 50, res.z), -Vector3.up, out hit, 70, mapLayer)) {
            Debug.LogWarning($"Altitude raycast missed at {res}");
            return 0;
        }

        return hit.point.y;
    }
    #endregion
}
