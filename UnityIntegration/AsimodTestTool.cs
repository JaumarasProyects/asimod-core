using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Tool for testing ASIMOD Core API directly from the Unity Inspector.
/// Attach this to the same GameObject as AsimodClient.
/// </summary>
[RequireComponent(typeof(AsimodClient))]
public class AsimodTestTool : MonoBehaviour
{
    private AsimodClient _client;

    [Header("Request Settings")]
    [TextArea(2, 5)]
    public string testPrompt = "Hello ASIMOD! Are you connected to Unity?";
    public string testModel = ""; 
    public string testProvider = "Ollama";
    public string testVoiceId = "1";

    [Header("Last Result (Read Only)")]
    public string status = "Idle";
    [TextArea(2, 5)]
    public string lastAiResponse = "";
    public string lastEmojis = "";

    void Awake()
    {
        _client = GetComponent<AsimodClient>();
    }

    private void Start()
    {
        if(_client == null) _client = GetComponent<AsimodClient>();
    }

    public void TestConnection()
    {
        status = "Testing connection...";
        _client.GetStatus(
            (res) => {
                status = "Connected!";
                Debug.Log($"[AsimodTest] Provider: {res.provider}, Model: {res.model}");
            },
            (err) => {
                status = "Error: " + err;
                Debug.LogError($"[AsimodTest] Connection Failed: {err}");
            }
        );
    }

    public void TestChat()
    {
        status = "Sending Chat...";
        lastAiResponse = "";
        lastEmojis = "";
        
        _client.SendChatMessage(testPrompt, testModel,
            (res) => {
                status = "Response Received!";
                lastAiResponse = res.response;
                lastEmojis = string.Join(", ", res.emojis);
                Debug.Log($"[AsimodTest] AI Response: {res.response}");
            },
            (err) => {
                status = "Chat Error: " + err;
                Debug.LogError($"[AsimodTest] Chat failed: {err}");
            }
        );
    }

    public void TestUpdateConfig()
    {
        string json = $"{{\"last_provider\": \"{testProvider}\", \"voice_id\": \"{testVoiceId}\"}}";
        status = "Updating Config...";
        _client.UpdateConfig(json,
            () => {
                status = "Config Updated!";
                Debug.Log("[AsimodTest] Config updated successfully!");
            },
            (err) => {
                status = "Config error: " + err;
                Debug.LogError($"[AsimodTest] Config update failed: {err}");
            }
        );
    }
}

// --- CUSTOM INSPECTOR GUI ---
#if UNITY_EDITOR
[CustomEditor(typeof(AsimodTestTool))]
public class AsimodTestToolEditor : Editor
{
    public override void OnInspectorGUI()
    {
        // Dibujar los campos normales (variables públicas)
        DrawDefaultInspector();

        AsimodTestTool tool = (AsimodTestTool)target;
        
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("API Actions", EditorStyles.boldLabel);

        if (GUILayout.Button("1. Test Connection", GUILayout.Height(30)))
        {
            tool.TestConnection();
        }

        EditorGUILayout.Space();

        GUI.backgroundColor = new Color(0.2f, 0.6f, 1.0f); // Azul para enviar
        if (GUILayout.Button("SEND CHAT PROMPT", GUILayout.Height(40)))
        {
            tool.TestChat();
        }
        GUI.backgroundColor = Color.white;

        EditorGUILayout.Space();

        if (GUILayout.Button("Update Provider/Voice"))
        {
            tool.TestUpdateConfig();
        }

        EditorGUILayout.HelpBox("Results will appear in the fields above during Play mode.", MessageType.Info);
    }
}
#endif
