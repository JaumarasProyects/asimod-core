using UnityEngine;
using System.Collections.Generic;
using System;

public class CharacterManager : MonoBehaviour
{
    [Header("Character List")]
    public List<CharacterData> characters = new List<CharacterData>();

    [Header("Active Character")]
    public CharacterData activeCharacter;

    [Header("ASIMOD Client")]
    public AsimodClient asimodClient;

    public Action<CharacterData> OnActiveCharacterChanged;

    private void Start()
    {
        if (asimodClient == null)
        {
            asimodClient = FindObjectOfType<AsimodClient>();
        }
        InitializeCharacters();
    }

    private void InitializeCharacters()
    {
        foreach (var character in characters)
        {
            EnsureThreadExists(character);
        }

        if (activeCharacter == null && characters.Count > 0)
        {
            SetActiveCharacter(characters[0]);
        }
    }

    private void EnsureThreadExists(CharacterData character)
    {
        if (character.HasValidThread())
        {
            asimodClient.CheckThreadExists(character.threadId, (exists) =>
            {
                if (exists)
                {
                    Debug.Log($"[CharacterManager] Thread '{character.threadId}' exists for '{character.characterName}'");
                }
                else
                {
                    Debug.Log($"[CharacterManager] Thread '{character.threadId}' not found, creating new thread...");
                    CreateNewThread(character);
                }
            }, (error) =>
            {
                Debug.LogError($"[CharacterManager] Error checking thread: {error}");
                CreateNewThread(character);
            });
            return;
        }

        Debug.Log($"[CharacterManager] No thread ID for '{character.characterName}', creating new thread...");
        CreateNewThread(character);
    }

    private void CreateNewThread(CharacterData character)
    {
        asimodClient.SetMemory(
            "New",
            character.characterName,
            character.personality,
            character.characterHistory,
            character.voiceId,
            character.voiceProvider,
            (newThreadId) => {
                character.threadId = newThreadId;
                Debug.Log($"[CharacterManager] Thread created: {newThreadId} for '{character.characterName}'");
            },
            (error) => {
                Debug.LogError($"[CharacterManager] Error creating thread: {error}");
            }
        );
    }

    public void SetActiveCharacter(CharacterData character)
    {
        if (!characters.Contains(character))
        {
            Debug.LogWarning($"[CharacterManager] Character not in list: {character.characterName}");
            return;
        }

        activeCharacter = character;
        asimodClient.SetMemory(
            character.threadId,
            character.characterName,
            character.personality,
            character.characterHistory,
            character.voiceId,
            character.voiceProvider,
            (threadId) => {
                Debug.Log($"[CharacterManager] Switched to character: {character.characterName}");
                OnActiveCharacterChanged?.Invoke(character);
            },
            (error) => {
                Debug.LogError($"[CharacterManager] Error switching character: {error}");
            }
        );
    }

    public void SwitchToCharacterByIndex(int index)
    {
        if (index >= 0 && index < characters.Count)
        {
            SetActiveCharacter(characters[index]);
        }
    }

    public CharacterData GetActiveCharacter()
    {
        return activeCharacter;
    }
}
