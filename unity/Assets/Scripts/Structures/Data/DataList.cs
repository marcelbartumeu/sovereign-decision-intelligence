using System;
using System.Collections.Generic;
using System.Globalization;
using System.Xml;
using UnityEngine;

[Serializable]
public struct XmlNameSpace {
    public string prefix;
    public string uri;

    public XmlNameSpace(string prefix, string uri) {
        this.prefix = prefix;
        this.uri = uri;
    }
}

public struct XmlTools {
    public XmlDocument doc;
    public XmlNamespaceManager nsmgr;
    public XmlNodeList nodeList;
}

[Serializable]
public abstract class DataList : ScriptableObject {
    public TextAsset asset;
    public List<Data> data = new();
    public List<XmlNameSpace> nameSpaces = new()
    {
        new XmlNameSpace("ogr", "http://ogr.maptools.org/"),
        new XmlNameSpace("gml", "http://www.opengis.net/gml/3.2")
    };
    public string nodeList = "";

    private void OnEnable() {
        CoordManager.OnLoadData += LoadData;
    }
    private void OnDisable() {
        CoordManager.OnLoadData -= LoadData;
    }

    public abstract void LoadData();

    protected XmlTools GetXmlTools() {
        XmlTools xmlTools = new();

        xmlTools.doc = CoordManager.instance.OpenXmlDoc(asset);

        if (xmlTools.doc == null) return xmlTools;

        if (nameSpaces.Count > 0) {
            xmlTools.nsmgr = new(xmlTools.doc.NameTable);

            foreach (XmlNameSpace nameSpace in nameSpaces) {
                xmlTools.nsmgr.AddNamespace(nameSpace.prefix, nameSpace.uri);
            }
            if (!string.IsNullOrEmpty(nodeList)) {
                xmlTools.nodeList = xmlTools.doc.SelectNodes(nodeList, xmlTools.nsmgr);
            }
        }
        else {
            xmlTools.nodeList = xmlTools.doc.SelectNodes(nodeList);
        }

        return xmlTools;
    }

    protected Vector3 GetGmlCoords(XmlElement element, XmlNamespaceManager nsmgr) {
        XmlNode node = element.SelectSingleNode(".//gml:lowerCorner", nsmgr);
        if (node == null) return Vector3.zero;

        string[] split = node.InnerText.Split(' ');
        Vector3 coord = GetCoordsByNodeStrings(split[0], split[1]);

        return coord;
    }

    protected Vector3 GetCoordsByNodeStrings(string latStr, string lonStr) {
        float.TryParse(latStr, NumberStyles.Any, CultureInfo.InvariantCulture, out float lat);
        float.TryParse(lonStr, NumberStyles.Any, CultureInfo.InvariantCulture, out float lon);

        return CoordManager.instance.CalculateXYPosition(lat, lon);
    }
}

public abstract class DataTrailList : DataList {
    protected Vector3 lastAdded;
    private const float minDistance = 0.3f;
    public bool isBackwards;

    protected bool DistanceChecker(Vector3 current) {
        if (Vector3.Distance(lastAdded, current) > minDistance) {
            lastAdded = current;
            return true;
        }
        else return false;
    }
}
