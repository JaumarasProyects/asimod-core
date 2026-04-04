using UnityEngine;

[CreateAssetMenu(fileName = "CharacterData", menuName = "ASIMOD/Character Data")]
public class CharacterData : ScriptableObject
{
    [Header("Character Info")]
    public string characterName = "New Character";
    public string personality = "";
    [TextArea(3, 10)]
    public string characterHistory = "";

    [Header("Voice Settings")]
    public string voiceProvider = "Edge TTS";
    public string voiceId = "";

    [Header("ASIMOD Thread ID")]
    public string threadId = "";

    [Header("Language")]
    public string language = "es";

    public bool HasValidThread()
    {
        return !string.IsNullOrEmpty(threadId) && threadId != "None";
    }
}
