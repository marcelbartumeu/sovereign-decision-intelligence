using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "featureMember", menuName = "Scriptable/Data/featureMember")]
public class featureMember : DataTrailList {

    public string _name;

    public override void LoadData() {

        XmlTools tools = GetXmlTools();
        data.Clear();

        if (tools.doc == null) return;

        tools.nodeList = tools.doc.SelectNodes("//ogr:featureMember/ogr:" + _name + "/ogr:geometryProperty/gml:Point/gml:pos", tools.nsmgr);
        bool isFirst = true;

        foreach (XmlElement element in tools.nodeList) {

            Data newData = new();

            string[] split = element.InnerText.Split(" ");
            newData.coord = GetCoordsByNodeStrings(split[0], split[1]);
            if (newData.coord == Vector3.zero) continue;

            if (isFirst) {
                lastAdded = newData.coord;
                isFirst = false;
            }

            if (DistanceChecker(newData.coord))
                data.Add(newData);
        }
    }
}
