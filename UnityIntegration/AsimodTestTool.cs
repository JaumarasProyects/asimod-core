using UnityEngine;

/// <summary>
/// Tool for testing ASIMOD Core API directly from the Unity Inspector.
/// Attach this to the same GameObject as AsimodClient.
/// </summary>
[RequireComponent(typeof(AsimodClient))]
public class AsimodTestTool : MonoBehaviour
{
    private AsimodClient _client;

    [Header("Test Settings")]
    public string testPrompt = "Hello ASIMOD! Are you connected to Unity?";
    public string testModel = ""; // Leave blank for default
    public string testProvider = "Ollama";
    public string testVoiceId = "1";

    void Awake()
    {
        _client = GetComponent<AsimodClient>();
    }

    [ContextMenu("1. Run Connection Test")]
    public void TestConnection()
    {
        Debug.Log("[AsimodTest] Testing connection...");
        _client.GetStatus(
            (status) => Debug.Log($"[AsimodTest] Success! Provider: {status.provider}, Model: {status.model}"),
            (error) => Debug.LogError($"[AsimodTest] Connection Failed: {error}")
        );
    }

    [ContextMenu("2. Run Chat Test")]
    public void TestChat()
    {
        Debug.Log($"[AsimodTest] Sending prompt: {testPrompt}");
        _client.SendChatMessage(testPrompt, testModel,
            (res) => {
                Debug.Log($"[AsimodTest] AI Response: {res.response}");
                Debug.Log($"[AsimodTest] Clean Text: {res.clean_text}");
                Debug.Log($"[AsimodTest] Emojis found: {string.Join(", ", res.emojis)}");
            },
            (error) => Debug.LogError($"[AsimodTest] Chat failed: {error}")
        );
    }

    [ContextMenu("3. Run Config Update Test")]
    public void TestUpdateConfig()
    {
        string json = $"{{\"last_provider\": \"{testProvider}\", \"voice_id\": \"{testVoiceId}\"}}";
        Debug.Log($"[AsimodTest] Updating config to: {json}");
        _client.UpdateConfig(json,
            () => Debug.Log("[AsimodTest] Config updated successfully!"),
            (error) => Debug.LogError($"[AsimodTest] Config update failed: {error}")
        );
    }

    [ContextMenu("4. Run Stop Audio Test")]
    public void TestStopAudio()
    {
        Debug.Log("[AsimodTest] Stopping remote audio...");
        _client.StopAudio(
            () => Debug.Log("[AsimodTest] Audio stop command sent."),
            (error) => Debug.LogError($"[AsimodTest] Stop audio failed: {error}")
        );
    }

    [ContextMenu("5. Run Mic Toggle Test (OFF then ON)")]
    public void TestMicToggle()
    {
        Debug.Log("[AsimodTest] Toggling Mic OFF...");
        _client.PauseMicrophone(() => {
            Debug.Log("[AsimodTest] Mic OFF. Resuming in 2 seconds...");
            Invoke("ResumeMic", 2.0f);
        });
    }

    private void ResumeMic()
    {
        _client.ResumeMicrophone(() => Debug.Log("[AsimodTest] Mic ON."));
    }
}
