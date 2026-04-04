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
    public string testVoiceProvider = "Edge TTS";
    public string testVoiceId = "1";

    [Header("Last Result (Read Only)")]
    public string status = "Idle";
    [TextArea(2, 5)]
    public string lastAiResponse = "";
    public string lastEmojis = "";

    [HideInInspector] public string[] availableProviders = new string[0];
    [HideInInspector] public string[] availableModels = new string[0];
    [HideInInspector] public string[] availableMemories = new string[0];
    [HideInInspector] public AsimodClient.VoiceEntry[] availableVoices = new AsimodClient.VoiceEntry[0];
    [HideInInspector] public AsimodClient.LanguageEntry[] availableLanguages = new AsimodClient.LanguageEntry[0];

    public string testMemory = "None";
    public string testLanguage = "es";
    public string testVoiceMode = "autoplay";
    public string testVoicePath = "audio";
    
    // Configuración para Nuevo Hilo
    public string testNewName = "";
    public string testNewPersonality = "";
    [TextArea(3, 10)] public string testNewHistory = "";
    public string testNewVoiceProvider = "Edge TTS";
    public string testNewVoiceId = "";

    private AsimodClient Client {
        get {
            if (_client == null) _client = GetComponent<AsimodClient>();
            return _client;
        }
    }

    public void RefreshProviders()
    {
        status = "Fetching providers...";
        Client.GetProviders(
            (res) => {
                availableProviders = res;
                status = "Providers refreshed!";
            },
            (err) => {
                status = "Error fetching providers: " + err;
            }
        );
    }

    public void RefreshModels()
    {
        status = "Fetching models...";
        Client.GetModels(testProvider,
            (res) => {
                availableModels = res;
                status = "Models refreshed!";
            },
            (err) => {
                status = "Error fetching models: " + err;
            }
        );
    }

    public void RefreshMemories()
    {
        status = "Fetching memories...";
        Client.GetMemories(
            (res) => {
                availableMemories = new string[res.Length + 2];
                availableMemories[0] = "None";
                availableMemories[1] = "New";
                System.Array.Copy(res, 0, availableMemories, 2, res.Length);
                status = "Memories refreshed!";
            },
            (err) => {
                status = "Error fetching memories: " + err;
            }
        );
    }

    public void RefreshVoices()
    {
        status = "Fetching voices...";
        Client.GetVoices(
            (res) => {
                availableVoices = res;
                status = "Voices refreshed!";
            },
            (err) => {
                status = "Error fetching voices: " + err;
            }
        );
    }

    public void RefreshLanguages()
    {
        status = "Fetching languages...";
        Client.GetLanguages(
            (res) => {
                availableLanguages = res;
                status = "Languages refreshed!";
            },
            (err) => {
                status = "Error fetching languages: " + err;
            }
        );
    }

    public void TestConnection()
    {
        status = "Testing connection...";
        Client.GetStatus(
            (res) => {
                status = "Connected!";
                testProvider = res.provider;
                testModel = res.model;
                testMemory = res.active_thread;
                testLanguage = res.language;
                testVoiceMode = res.voice_mode;
                testVoicePath = res.voice_path;
                testVoiceId = res.voice_id;
                testVoiceProvider = res.voice_provider;
                Debug.Log($"[AsimodTest] Connected to {res.active_thread} thread. Language: {res.language}, VoiceMode: {res.voice_mode}, VoicePath: {res.voice_path}");
            },
            (err) => {
                status = "Error: " + err;
            }
        );
    }

    public void TestSetLanguage()
    {
        status = "Setting language...";
        Client.SetLanguage(testLanguage,
            () => {
                status = "Language set to: " + testLanguage;
            },
            (err) => {
                status = "Error setting language: " + err;
            }
        );
    }

    public void TestChat()
    {
        status = "Sending Chat...";
        Client.SendChatMessage(testPrompt, testModel,
            (res) => {
                status = "Response Received!";
                lastAiResponse = res.response;
                lastEmojis = string.Join(", ", res.emojis);
            },
            (err) => {
                status = "Chat Error: " + err;
            }
        );
    }

    public void TestUpdateConfig()
    {
        string json = $"{{\"last_provider\": \"{testProvider}\", \"last_model\": \"{testModel}\", \"voice_id\": \"{testVoiceId}\", \"voice_provider\": \"{testVoiceProvider}\", \"voice_mode\": \"{testVoiceMode}\", \"voice_save_path\": \"{testVoicePath}\"}}";
        status = "Updating Config...";
        Client.UpdateConfig(json,
            () => {
                status = "Config Updated!";
            },
            (err) => {
                status = "Config error: " + err;
            }
        );
    }

    public void StopAudio()
    {
        status = "Stopping remote audio...";
        Client.StopAudio(() => status = "Audio stopped!", (err) => status = "Error: " + err);
    }

    public void UpdateCurrentProfile()
    {
        status = "Updating profile...";
        Client.UpdateProfile(testNewName, testNewPersonality, testNewHistory, testVoiceId, testProvider, () => {
            status = "Profile updated!";
            RefreshMemories();
        }, (err) => status = "Error: " + err);
    }

    public void SwitchMemory(string threadId)
    {
        status = "Switching memory...";
        
        string name = (threadId == "New") ? testNewName : null;
        string pers = (threadId == "New") ? testNewPersonality : null;
        string hist = (threadId == "New") ? testNewHistory : null;
        string voice = (threadId == "New") ? testNewVoiceId : null;
        string prov = (threadId == "New") ? testNewVoiceProvider : null;

        Client.SetMemory(threadId, name, pers, hist, voice, prov, (newId) => {
            testMemory = newId;
            status = "Memory: " + newId;
            RefreshMemories();
            // Al cambiar, sincronizar estado para ver si el personaje trajo su propia voz/motor
            TestConnection(); 
        }, (err) => status = "Error: " + err);
    }
}

// --- CUSTOM INSPECTOR GUI ---
#if UNITY_EDITOR
[CustomEditor(typeof(AsimodTestTool))]
public class AsimodTestToolEditor : Editor
{
    private bool showNewThreadSetup = false;

    public override void OnInspectorGUI()
    {
        AsimodTestTool tool = (AsimodTestTool)target;
        
        // Preparar nombres de voces para popups
        string[] voiceNames = new string[tool.availableVoices.Length];
        for(int i=0; i<voiceNames.Length; i++) voiceNames[i] = tool.availableVoices[i].name;

        EditorGUILayout.LabelField("Memory & Persona", EditorStyles.boldLabel);
        
        // Configuración de Nuevo Hilo
        showNewThreadSetup = EditorGUILayout.Foldout(showNewThreadSetup, "New Thread / Persona Setup");
        if (showNewThreadSetup)
        {
            EditorGUI.indentLevel++;
            tool.testNewName = EditorGUILayout.TextField("Name", tool.testNewName);
            tool.testNewPersonality = EditorGUILayout.TextField("Personality", tool.testNewPersonality);
            tool.testNewHistory = EditorGUILayout.TextArea(tool.testNewHistory, GUILayout.Height(60));
            
            // Selector de motor para el nuevo hilo
            if (tool.availableProviders.Length > 0)
            {
                int npIdx = Mathf.Max(0, System.Array.IndexOf(tool.availableProviders, tool.testNewVoiceProvider));
                tool.testNewVoiceProvider = tool.availableProviders[EditorGUILayout.Popup("Voice Engine", npIdx, tool.availableProviders)];
            }

            // Selector de voz para el nuevo hilo
            if (tool.availableVoices.Length > 0)
            {
                int nvIdx = -1;
                for(int i=0; i<tool.availableVoices.Length; i++) if(tool.availableVoices[i].id == tool.testNewVoiceId) nvIdx = i;
                int newNVIdx = EditorGUILayout.Popup("Default Voice", Mathf.Max(0, nvIdx), voiceNames);
                tool.testNewVoiceId = tool.availableVoices[newNVIdx].id;
            }
            else tool.testNewVoiceId = EditorGUILayout.TextField("Voice ID", tool.testNewVoiceId);
            
            if (GUILayout.Button("Update Current Profile (💾)")) tool.UpdateCurrentProfile();
            EditorGUI.indentLevel--;
        }

        EditorGUILayout.BeginHorizontal();
        int memIndex = Mathf.Max(0, System.Array.IndexOf(tool.availableMemories, tool.testMemory));
        if (tool.availableMemories.Length > 0)
        {
            int newIdx = EditorGUILayout.Popup("Active Memory", memIndex, tool.availableMemories);
            if (newIdx != memIndex) tool.SwitchMemory(tool.availableMemories[newIdx]);
        }
        else EditorGUILayout.LabelField("Load memories first ->");
        if (GUILayout.Button("🔄", GUILayout.Width(30))) tool.RefreshMemories();
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Language & Settings", EditorStyles.boldLabel);
        
        // Language Selector
        if (tool.availableLanguages == null || tool.availableLanguages.Length == 0)
        {
            EditorGUILayout.LabelField("Language", "No languages loaded (click 🔄)");
            tool.testLanguage = EditorGUILayout.TextField("Language", tool.testLanguage);
        }
        else
        {
            string[] languageNames = new string[tool.availableLanguages.Length];
            for(int i=0; i<languageNames.Length; i++) languageNames[i] = tool.availableLanguages[i].name;
            
            EditorGUILayout.BeginHorizontal();
            int langIdx = -1;
            for(int i=0; i<tool.availableLanguages.Length; i++) if(tool.availableLanguages[i].code == tool.testLanguage) langIdx = i;
            
            int newLangIdx = EditorGUILayout.Popup("Language", Mathf.Max(0, langIdx), languageNames);
            tool.testLanguage = tool.availableLanguages[newLangIdx].code;
            EditorGUILayout.EndHorizontal();
        }
        
        if (GUILayout.Button("🔄 Refresh Languages", GUILayout.Width(150))) tool.RefreshLanguages();
        
        if (GUILayout.Button("Set Language")) tool.TestSetLanguage();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("AI Motor (Global Context)", EditorStyles.boldLabel);
        
        // Provider
        EditorGUILayout.BeginHorizontal();
        int pIdx = Mathf.Max(0, System.Array.IndexOf(tool.availableProviders, tool.testProvider));
        if (tool.availableProviders.Length > 0)
            tool.testProvider = tool.availableProviders[EditorGUILayout.Popup("LLM Provider", pIdx, tool.availableProviders)];
        else tool.testProvider = EditorGUILayout.TextField("LLM Provider", tool.testProvider);
        if (GUILayout.Button("🔄", GUILayout.Width(30))) tool.RefreshProviders();
        EditorGUILayout.EndHorizontal();

        // Model
        EditorGUILayout.BeginHorizontal();
        int mIdx = Mathf.Max(0, System.Array.IndexOf(tool.availableModels, tool.testModel));
        if (tool.availableModels.Length > 0)
            tool.testModel = tool.availableModels[EditorGUILayout.Popup("LLM Model", mIdx, tool.availableModels)];
        else tool.testModel = EditorGUILayout.TextField("LLM Model", tool.testModel);
        if (GUILayout.Button("🔄", GUILayout.Width(30))) tool.RefreshModels();
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Voice Output (Global/Temporary)", EditorStyles.boldLabel);
        
        // Voice Mode (autoplay/path)
        string[] voiceModes = new string[] { "autoplay", "path" };
        int vmIdx = System.Array.IndexOf(voiceModes, tool.testVoiceMode);
        if (vmIdx < 0) vmIdx = 0;
        tool.testVoiceMode = voiceModes[EditorGUILayout.Popup("Voice Mode", vmIdx, voiceModes)];
        
        // Voice Path
        tool.testVoicePath = EditorGUILayout.TextField("Voice Path", tool.testVoicePath);
        
        // Motor de Voz Global
        EditorGUILayout.BeginHorizontal();
        if (tool.availableProviders.Length > 0) // Usamos la misma lista de proveedores para elegir motor de voz
        {
            int vpIdx = Mathf.Max(0, System.Array.IndexOf(tool.availableProviders, tool.testVoiceProvider));
            tool.testVoiceProvider = tool.availableProviders[EditorGUILayout.Popup("TTS Provider", vpIdx, tool.availableProviders)];
        }
        else tool.testVoiceProvider = EditorGUILayout.TextField("TTS Provider", tool.testVoiceProvider);
        
        if (GUILayout.Button("🔄", GUILayout.Width(30))) tool.RefreshVoices();
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal();
        int vIdx = -1;
        for(int i=0; i<tool.availableVoices.Length; i++) if(tool.availableVoices[i].id == tool.testVoiceId) vIdx = i;

        if (tool.availableVoices.Length > 0)
        {
            int newVIdx = EditorGUILayout.Popup("Active Voice", Mathf.Max(0, vIdx), voiceNames);
            tool.testVoiceId = tool.availableVoices[newVIdx].id;
        }
        else tool.testVoiceId = EditorGUILayout.TextField("Voice ID", tool.testVoiceId);
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Testing & Actions", EditorStyles.boldLabel);
        tool.testPrompt = EditorGUILayout.TextArea(tool.testPrompt, GUILayout.Height(60));

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Status: " + tool.status);
        EditorGUILayout.SelectableLabel(tool.lastAiResponse, EditorStyles.textArea, GUILayout.Height(60));

        EditorGUILayout.Space();
        if (GUILayout.Button("1. Sync State (from Remote)", GUILayout.Height(30))) tool.TestConnection();
        
        GUI.backgroundColor = new Color(0.2f, 0.6f, 1.0f);
        if (GUILayout.Button("SEND CHAT PROMPT", GUILayout.Height(40))) tool.TestChat();
        GUI.backgroundColor = Color.white;

        if (GUILayout.Button("Apply Motor/Voice to Remote")) tool.TestUpdateConfig();
        
        GUI.backgroundColor = new Color(1.0f, 0.3f, 0.3f);
        if (GUILayout.Button("STOP REMOTE AUDIO", GUILayout.Height(30))) tool.StopAudio();
        GUI.backgroundColor = Color.white;

        if (GUI.changed) EditorUtility.SetDirty(tool);
    }
}
#endif
