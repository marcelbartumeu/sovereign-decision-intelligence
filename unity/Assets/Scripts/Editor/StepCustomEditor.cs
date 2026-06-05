using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
//using UnityEditorInternal;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditorInternal;
[CustomEditor(typeof(VideoManager))]
public class StepCustomEditor : Editor {
    ReorderableList stepsReorList;

    SerializedProperty stepsListProp;
    SerializedProperty paintsListProp;

    VideoManager videoManager;

    float lineHeight;
    float lineHeightSpace;
    float emptyListHeight;

    private readonly Dictionary<string, ReorderableList> paintsListDict = new();

    private void OnEnable() {

        if (target == null) return;

        videoManager = (VideoManager)target;

        // Retrieve "steps" property
        stepsListProp = serializedObject.FindProperty("steps");

        lineHeight = EditorGUIUtility.singleLineHeight;
        lineHeightSpace = 2;
        emptyListHeight = 4;

        GUIStyle boldStyle = new GUIStyle {
            fontStyle = FontStyle.Bold,
            normal = { textColor = Color.white }
        };

        // Creates ReorderableList with 
        //    - SerializedObject beeing the VideoManager object: Needed to detect and apply 
        //      changes to the "steps" list
        //    - StepsListProp beeind the "steps" list property: Needed to access the individual steps
        //      for display and modifications
        stepsReorList = new ReorderableList(serializedObject, stepsListProp, true, true, true, true) {
            drawHeaderCallback = DrawStepsHeader,
            drawElementCallback = DrawStepsList,
            elementHeightCallback = SetStepsHeigh
        };
    }
    private void OnDisable() {
        foreach (ReorderableList list in paintsListDict.Values) {
            list.serializedProperty?.serializedObject?.Dispose();
        }
        paintsListDict.Clear();
    }

    private void DrawStepsList(Rect rect, int index, bool isActive, bool isFocused) {
        float stepLines = 1;

        // Get the Step property with the given index
        SerializedProperty stepProp = stepsListProp.GetArrayElementAtIndex(index);
        if (stepProp == null || stepProp.objectReferenceValue == null) return;

        string paintListKey;

        // Get the Step object referenced by stepProp so we can work with the 
        // Step properties
        // This line is needed because Step is a Scriptable Object (extern)
        SerializedObject stepObj = new SerializedObject(stepProp.objectReferenceValue);

        try {
            // Get the last version of this object
            stepObj.Update();

            DrawStepHeader(rect, stepObj, stepProp);

            // Get the Paint property from the Step object
            paintsListProp = stepObj.FindProperty("paints");

            // Store the property path of the Step object for later use
            paintListKey = stepProp.propertyPath;

            if (stepObj.FindProperty("showStepEditor").boolValue)
                DrawStepContent(rect, stepObj, stepProp, paintListKey, ref stepLines);

            stepObj.ApplyModifiedProperties();
        } finally {
            if (!paintsListDict.ContainsKey(stepProp.propertyPath)) {
                stepObj.Dispose();
            }
        }
    }

    private void DrawStepHeader(Rect rect, SerializedObject stepObj, SerializedProperty stepProp) {
        ScriptableObject scriptable;

        EditorGUILayout.BeginHorizontal();
        // Get the ScriptableObject representing that step property
        scriptable = (ScriptableObject)stepProp.objectReferenceValue;
        // Get the name of the ScriptableObject
        string name = scriptable.name.ToString().Split("Step")[0];

        // Set "showStepEditor" property value depending on the Foldout return value
        stepObj.FindProperty("showStepEditor").boolValue = EditorGUI.Foldout(new Rect(rect.x + 20, rect.y, rect.width, lineHeight),
                                                                stepObj.FindProperty("showStepEditor").boolValue,
                                                                name);
        // Draw a green rect if is "toShow" and red if not
        EditorGUI.DrawRect(new Rect(rect.x + 200, rect.y + lineHeight / 2, 5, 5),
                            stepObj.FindProperty("toShow").boolValue ? Color.green : Color.red);
        EditorGUILayout.EndHorizontal();
    }


    private void DrawStepContent(Rect rect, SerializedObject stepObj, SerializedProperty stepProp, string paintListKey, ref float stepLines) {

        DrawField(rect, 0, stepObj.FindProperty("toShow"), ref stepLines);
        DrawField(rect, 0, stepObj.FindProperty("cleanPrevious"), ref stepLines);


        DrawField(rect, 0, stepObj.FindProperty("isLayer"), ref stepLines);
        if (stepObj.FindProperty("isLayer").boolValue) {
            DrawField(rect, 1, stepObj.FindProperty("baseMaterial"), ref stepLines);
            DrawField(rect, 1, stepObj.FindProperty("layerMaterial"), ref stepLines);
            DrawField(rect, 1, stepObj.FindProperty("layerOpacity"), ref stepLines);
        }

        DrawField(rect, 0, stepObj.FindProperty("sprite"), ref stepLines);

        DrawField(rect, 0, stepObj.FindProperty("isRightLeftText"), ref stepLines);
        if (stepObj.FindProperty("isRightLeftText").boolValue) {
            DrawField(rect, 1, stepObj.FindProperty("textKey"), ref stepLines);
        }

        ReorderableList paintsReorList;
        DrawField(rect, 0, stepObj.FindProperty("isPaint"), ref stepLines);
        if (stepObj.FindProperty("isPaint").boolValue) {

            if (paintsListDict.ContainsKey(paintListKey)) {
                paintsReorList = paintsListDict[paintListKey];

            } else {

                paintsReorList = new ReorderableList(stepProp.serializedObject, paintsListProp, true, true, true, true);

                paintsReorList.drawHeaderCallback = DrawDataHeader;
                paintsReorList.drawElementCallback = DrawPaintList;
                paintsReorList.elementHeightCallback = SetPaintHeigh;
                paintsReorList.onAddDropdownCallback = AddPaint;
                paintsReorList.onRemoveCallback = RemovePaint;
                paintsListDict.TryAdd(paintListKey, paintsReorList);
            }
            paintsReorList.DoList(new Rect(rect.x, rect.y + lineHeight + stepLines * lineHeight, rect.width, 40));

            SerializedProperty paint = stepObj.FindProperty("paints");

            for (int i = 0; i < paint.arraySize; i++) {
                SerializedProperty element = paint.GetArrayElementAtIndex(i);
                stepLines += GetPaintsHeight(element);
            }
            stepLines += 3;
        }

        DrawField(rect, 0, stepObj.FindProperty("hasAnim"), ref stepLines);
        if (stepObj.FindProperty("hasAnim").boolValue) {

            SerializedProperty iterator = stepObj.FindProperty("anim");
            SerializedProperty endProperty = iterator.GetEndProperty();

            iterator.NextVisible(true);

            while (!SerializedProperty.EqualContents(iterator, endProperty)) {
                DrawField(rect, 1, iterator, ref stepLines);
                iterator.NextVisible(true);
            }
        }

        DrawField(rect, 0, stepObj.FindProperty("displayTime"), ref stepLines);
    }


    private float SetStepsHeigh(int index) {

        #region INITIALIZE
        SerializedProperty stepProp;
        SerializedObject stepObj;

        SerializedProperty iterator;
        try {
            stepProp = stepsListProp.GetArrayElementAtIndex(index);
            // Need the step object because Step is a Scriptable Object
            stepObj = new SerializedObject(stepProp.objectReferenceValue);
            stepObj.Update();

            iterator = stepObj.GetIterator();
        } catch {
            return 0;
        }
        #endregion

        float height = 1;

        if (stepObj.FindProperty("showStepEditor").boolValue) {

            height += 8;

            if (stepObj.FindProperty("isLayer").boolValue) {
                height += 3 + GetArrayLines(stepObj.FindProperty("layerMaterial"));
            }

            if (stepObj.FindProperty("isRightLeftText").boolValue)
                height++;

            SerializedProperty paint = stepObj.FindProperty("paints");
            if (stepObj.FindProperty("isPaint").boolValue) {
                float paintsHeight = emptyListHeight;

                for (int i = 0; i < paint.arraySize; i++) {
                    SerializedProperty element = paint.GetArrayElementAtIndex(i);
                    paintsHeight += GetPaintsHeight(element);
                }
                height += paintsHeight - 1;
            }

            if (stepObj.FindProperty("hasAnim").boolValue)
                height += 7;
        }

        return lineHeight * height + lineHeightSpace * height - 1; // Altura dinámica basada en el número de líneas
    }

    private void DrawStepsHeader(Rect rect) {
        EditorGUI.LabelField(rect, "Steps");
    }

    private void DrawPaintList(Rect rect, int index, bool isActive, bool isFocused) {

        float paintLines = 0;

        if (paintsListProp == null || index >= paintsListProp.arraySize) return;

        SerializedProperty paintProp = paintsListProp.GetArrayElementAtIndex(index);
        if (paintProp == null) return;

        SerializedProperty toShow = paintProp.FindPropertyRelative("showPaintEditor");

        SerializedProperty endProp = paintProp.GetEndProperty();
        EditorGUILayout.BeginHorizontal();
        paintProp.NextVisible(true);
        paintProp.boolValue = EditorGUI.Foldout(new Rect(rect.x + 20, rect.y, rect.width, lineHeight),
                                                                paintProp.boolValue,
                                                                name);
        paintProp.NextVisible(true);
        EditorGUI.LabelField(new Rect(rect.x + 25, rect.y + (lineHeight * paintLines + lineHeightSpace * paintLines - 1),
                            200, lineHeight),
                            "Drawing Time: " + paintProp.stringValue);
        EditorGUILayout.EndHorizontal();
        paintLines++;

        if (toShow == null) return;

        if (toShow.boolValue) {
            paintProp.NextVisible(true);

            while (!SerializedProperty.EqualContents(endProp, paintProp)) {
                DrawField(rect, 1, paintProp, ref paintLines);
                paintProp.NextVisible(true);
            }

            paintLines += 0.2f;
            if (GUI.Button(new Rect(rect.x + 75, rect.y + (lineHeight * paintLines + lineHeightSpace * paintLines - 1),
                                    200, lineHeight), "Update Drawing Time")) {
                paintProp = paintsListProp.GetArrayElementAtIndex(index);
                paintProp.FindPropertyRelative("drawingTime").stringValue = GetPaintDrawingTime(paintProp);
            }
        }
    }

    private string GetPaintDrawingTime(SerializedProperty paintProp) {
        float speed = paintProp.FindPropertyRelative("speed").floatValue;
        SerializedProperty toPaintProp = paintProp.FindPropertyRelative("toPaint");

        if (toPaintProp.objectReferenceValue == null)
            return "_";

        using SerializedObject dataListObj = new SerializedObject(toPaintProp.objectReferenceValue);
        SerializedProperty dataArrayProp = dataListObj.FindProperty("data");

        // Update the SerializedObject to get current values
        dataListObj.Update();
        return (speed * dataArrayProp.arraySize).ToString();
    }

    private void DrawDataHeader (Rect rect) {
        EditorGUI.LabelField(rect, "Paints");
    }

    private float SetPaintHeigh(int index) {
        float height = 0;

        if (paintsListProp == null || index >= paintsListProp.arraySize) return height;

        SerializedProperty paintProp = paintsListProp.GetArrayElementAtIndex(index);
        if (paintProp == null) return height;

        height = GetPaintsHeight(paintProp);
        return lineHeight * height + lineHeightSpace * height - 1; // Altura dinámica basada en el número de líneas
    }

    private float GetPaintsHeight(SerializedProperty paintProp) {
        float height = 0;
        SerializedProperty toShow = paintProp.FindPropertyRelative("showPaintEditor");
        if (toShow == null) return 1;

        if (!toShow.boolValue)
            return 1;

        SerializedProperty endProp = paintProp.GetEndProperty();
        paintProp.NextVisible(true);

        while (!SerializedProperty.EqualContents(endProp, paintProp)) {
            paintProp.NextVisible(true);
            height++;
        }

        return height;
    }

    private void AddPaint(Rect buttonRect, ReorderableList list) {
        GenericMenu menu = new GenericMenu();

        Type baseType = typeof(PaintType);

        // Get all the subclassses
        IEnumerable<Type> subclasses = TypeCache.GetTypesDerivedFrom(baseType)
        .Where(t => !t.IsAbstract);

        foreach (Type subclass in subclasses) {
            menu.AddItem(
                new GUIContent(subclass.Name),
                false,
                () => AddSubclassInstance(list, subclass)
            );
        }

        menu.ShowAsContext();
    }

    private void AddSubclassInstance(ReorderableList list, Type subclass) {
        SerializedObject stepComponent = list.serializedProperty.serializedObject;
        stepComponent.Update();

        // Add new element to array
        int newIndex = list.serializedProperty.arraySize;
        list.serializedProperty.arraySize++;
        stepComponent.ApplyModifiedProperties();

        // Get reference to the new element
        SerializedProperty newElement = list.serializedProperty.GetArrayElementAtIndex(newIndex);

        // Create instance and assign as managed reference
        object newInstance = Activator.CreateInstance(subclass);
        newElement.managedReferenceValue = newInstance;

        stepComponent.ApplyModifiedProperties();
    }


    private void RemovePaint(ReorderableList list) {
        if (list.serializedProperty == null)
            return;

        list.serializedProperty.serializedObject.Update();
        ReorderableList.defaultBehaviours.DoRemoveButton(list);
        list.serializedProperty.serializedObject.ApplyModifiedProperties();

    }
    private void DrawField(Rect rect, int lvl, SerializedProperty property, ref float lines) {
        EditorGUI.indentLevel += lvl;
        EditorGUI.PropertyField(new Rect(rect.x, rect.y + (lineHeight * lines + lineHeightSpace * lines - 1), rect.width, lineHeight), 
                                property, 
                                new GUIContent(property.displayName));
        EditorGUI.indentLevel -= lvl;

        lines += 1 + GetArrayLines(property);
    }

    private float GetArrayLines(SerializedProperty property) {
        float arrayLines = 0;
        if (property.isArray && property.isExpanded)
            arrayLines = Mathf.Clamp(property.arraySize, 1, property.arraySize) + 1.5f;

        return arrayLines;
    }

    private void CollapseAll() {
        foreach (Step step in videoManager.steps) {
            step.showStepEditor = false;
        }
    }

    public override void OnInspectorGUI() {
        base.OnInspectorGUI();
        GUILayout.Space(10);
        serializedObject.Update();
        GUILayout.Label("Total time: " + videoManager.GetTotalTime().ToString("n2"));
        stepsReorList.DoLayoutList();
        serializedObject.ApplyModifiedProperties();
        EditorGUILayout.BeginHorizontal();
        GUILayout.FlexibleSpace();
        if (GUILayout.Button("Collapse All", GUILayout.Width(200))) {
            CollapseAll();
        }
        GUILayout.FlexibleSpace();
        EditorGUILayout.EndHorizontal();
    }

}
#endif