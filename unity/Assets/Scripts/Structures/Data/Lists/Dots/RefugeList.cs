using System.Globalization;
using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "Refuges", menuName = "Scriptable/Data/Refuges")]
public class RefugeList : DataList {
    [Space]
    public Sprite refugeSprite;
    [Space]
    public Color guardedColor;
    public Color notGuardedColor;

    public override void LoadData() {
        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {

            Data newData = new();

            // Coord
            Vector3 coord = GetCoordsByNodeStrings(element.GetAttribute("lat"), element.GetAttribute("lon"));
            newData.coord = coord;
            if (newData.coord == Vector3.zero) continue;

            // Name
            XmlNode nameNode = element.SelectSingleNode("gpx:nom", tools.nsmgr);
            if (nameNode != null) newData.AddField(Types.Name, nameNode.InnerText);
            else Debug.LogWarning("null nameNode");

            // Altitud
            XmlNode altitudNode = element.SelectSingleNode("gpx:altitud", tools.nsmgr);
            if (altitudNode != null) {
                float.TryParse(altitudNode.InnerText, NumberStyles.Any, CultureInfo.InvariantCulture, out float altitud);
                newData.AddField(Types.Altitud, altitud);
            }
            else Debug.LogWarning("null altitudNode");


            // Guarded Check
            XmlNode guardedNode = element.SelectSingleNode("gpx:tipus", tools.nsmgr);
            if (guardedNode != null) {
                bool guarded = !guardedNode.InnerText.Contains("no");
                newData.AddField(Types.Guarded, guarded);
                newData.AddField(Types.Color, guarded ? guardedColor : notGuardedColor);
            }
            else Debug.LogWarning("null guardedNode");

            // Sprite
            newData.AddField(Types.Sprite, refugeSprite);

            data.Add(newData);
        }
    }
}
