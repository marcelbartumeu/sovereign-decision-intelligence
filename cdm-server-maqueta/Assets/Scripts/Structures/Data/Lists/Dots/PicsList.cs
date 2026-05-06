using System.Globalization;
using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "Pics", menuName = "Scriptable/Data/Pics")]
public class PicsList : DataList {
    public float minAltitud;
    public Color comaColor;
    public float comaSize;
    public override void LoadData() {

        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {

            Data newData = new();

            // Altitud
            XmlNode altitudNode = element.SelectSingleNode(".//ogr:ALCADA", tools.nsmgr);
            if (altitudNode != null) {
                float.TryParse(altitudNode.InnerText, NumberStyles.Any, CultureInfo.InvariantCulture, out float altitud);

                if (altitud <= minAltitud) continue;
                newData.AddField(Types.Altitud, altitud);
            }


            // Coord
            newData.coord = GetGmlCoords(element, tools.nsmgr);
            if (newData.coord == Vector3.zero) continue;

            // Name
            XmlNode nameNode = element.SelectSingleNode(".//ogr:NOM_PICS", tools.nsmgr);
            if (nameNode != null) {
                newData.AddField(Types.Name, nameNode.InnerText);

                // Coma Pedrosa Exception
                if (nameNode.InnerText == "Pic de Coma Pedrosa") {
                    newData.AddField(Types.Color, comaColor);
                    newData.AddField(Types.Size, comaSize);
                    newData.coord = new Vector3(newData.coord.x - 0.5f, newData.coord.y, newData.coord.z - 1.5f);

                }
            }

            data.Add(newData);
        }
    }
}
