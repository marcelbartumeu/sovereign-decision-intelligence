using System.Xml;
using UnityEngine;


[CreateAssetMenu(fileName = "Nuclis", menuName = "Scriptable/Data/Nuclis")]
public class NuclisList : DataList {
    [Space]
    public float parSize;
    public float nucSize;
    [Space]
    public Color parColor;
    public Color nucColor;
    [Space]
    public string parName;

    public override void LoadData() {
        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {

            XmlNode node = element.SelectSingleNode(".//ogr:PARROQUIA", tools.nsmgr);
            if (node == null) continue;
            if (node.InnerText != parName) continue;

            Data newData = new();

            // Coord
            newData.coord = GetGmlCoords(element, tools.nsmgr);
            if (newData.coord == Vector3.zero) continue;

            XmlNode nameNode = element.SelectSingleNode(".//ogr:POBLACIO", tools.nsmgr);
            if (nameNode != null) {
                // Check if is main town
                if (nameNode.InnerText == node.InnerText) {
                    newData.AddField(Types.Size, parSize);
                    newData.AddField(Types.Color, parColor);
                }
                else {
                    newData.AddField(Types.Size, nucSize);
                    newData.AddField(Types.Color, nucColor);
                }
            }


            data.Add(newData);
        }
    }
}
