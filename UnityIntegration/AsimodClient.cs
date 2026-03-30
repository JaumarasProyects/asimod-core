using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// ASIMOD Core Client for Unity
/// This script handles all communication with the ASIMOD Core API.
/// </summary>
public class AsimodClient : MonoBehaviour
{
    [Header("Configuration")]
    public string apiBaseUrl = "http://localhost:8000/v1";

    #region Data Structures (JSON)

    [Serializable]
    public class ChatRequest
    {
        public string text;
        public string model;
    }

    [Serializable]
    public class ChatResponse
    {
        public string response;
        public string clean_text;
        public string[] emojis;
        public string status;
    }

    [Serializable]
    public class StatusResponse
    {
        public string provider;
        public string model;
        public string voice_provider;
        public string voice_mode;
        public string stt_mode;
    }

    [Serializable]
    public class VoiceProvidersResponse
    {
        public string[] voice_providers;
    }

    [Serializable]
    public class VoiceEntry
    {
        public string id;
        public string name;
        public string language;
        public string detail;
    }

    [Serializable]
    public class VoicesResponse
    {
        public VoiceEntry[] voices;
    }

    #endregion

    #region Public API Methods

    /// <summary>
    /// Sends a message to the AI and returns the response via callback.
    /// </summary>
    public void SendChatMessage(string text, string model, Action<ChatResponse> onSuccess, Action<string> onError)
    {
        ChatRequest req = new ChatRequest { text = text, model = model };
        string json = JsonUtility.ToJson(req);
        StartCoroutine(PostRequest("/chat", json, (res) => {
            ChatResponse chatRes = JsonUtility.FromJson<ChatResponse>(res);
            onSuccess?.Invoke(chatRes);
        }, onError));
    }

    /// <summary>
    /// Gets the current system status.
    /// </summary>
    public void GetStatus(Action<StatusResponse> onSuccess, Action<string> onError)
    {
        StartCoroutine(GetRequest("/status", (res) => {
            StatusResponse status = JsonUtility.FromJson<StatusResponse>(res);
            onSuccess?.Invoke(status);
        }, onError));
    }

    /// <summary>
    /// Lists all available Voice Providers (TTS Engines).
    /// </summary>
    public void GetVoiceProviders(Action<string[]> onSuccess, Action<string> onError)
    {
        StartCoroutine(GetRequest("/voice_providers", (res) => {
            VoiceProvidersResponse vRes = JsonUtility.FromJson<VoiceProvidersResponse>(res);
            onSuccess?.Invoke(vRes.voice_providers);
        }, onError));
    }

    /// <summary>
    /// Lists all available voices for the current voice provider.
    /// </summary>
    public void GetVoices(Action<VoiceEntry[]> onSuccess, Action<string> onError)
    {
        StartCoroutine(GetRequest("/voices", (res) => {
            VoicesResponse vRes = JsonUtility.FromJson<VoicesResponse>(res);
            onSuccess?.Invoke(vRes.voices);
        }, onError));
    }

    /// <summary>
    /// Updates the remote configuration (e.g., switches provider or voice).
    /// </summary>
    public void UpdateConfig(string jsonConfig, Action onSuccess, Action<string> onError)
    {
        StartCoroutine(PostRequest("/config", jsonConfig, (res) => onSuccess?.Invoke(), onError));
    }

    /// <summary>
    /// Stops any audio currently playing on the ASIMOD Core PC.
    /// </summary>
    public void StopAudio(Action onSuccess = null, Action<string> onError = null)
    {
        StartCoroutine(PostRequest("/audio/stop", "{}", (res) => onSuccess?.Invoke(), onError));
    }

    /// <summary>
    /// Pauses ASIMOD Core microphone capture.
    /// </summary>
    public void PauseMicrophone(Action onSuccess = null, Action<string> onError = null)
    {
        StartCoroutine(PostRequest("/audio/pause", "{}", (res) => onSuccess?.Invoke(), onError));
    }

    /// <summary>
    /// Resumes ASIMOD Core microphone capture.
    /// </summary>
    public void ResumeMicrophone(Action onSuccess = null, Action<string> onError = null)
    {
        StartCoroutine(PostRequest("/audio/resume", "{}", (res) => onSuccess?.Invoke(), onError));
    }

    #endregion

    #region Generic Web Request Helpers

    private IEnumerator GetRequest(string endpoint, Action<string> onSuccess, Action<string> onError)
    {
        using (UnityWebRequest webRequest = UnityWebRequest.Get(apiBaseUrl + endpoint))
        {
            yield return webRequest.SendWebRequest();

            if (webRequest.result == UnityWebRequest.Result.Success)
                onSuccess?.Invoke(webRequest.downloadHandler.text);
            else
                onError?.Invoke(webRequest.error);
        }
    }

    private IEnumerator PostRequest(string endpoint, string json, Action<string> onSuccess, Action<string> onError)
    {
        var webRequest = new UnityWebRequest(apiBaseUrl + endpoint, "POST");
        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);
        webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
        webRequest.downloadHandler = new DownloadHandlerBuffer();
        webRequest.SetRequestHeader("Content-Type", "application/json");

        yield return webRequest.SendWebRequest();

        if (webRequest.result == UnityWebRequest.Result.Success)
            onSuccess?.Invoke(webRequest.downloadHandler.text);
        else
            onError?.Invoke(webRequest.error);
    }

    #endregion
}
