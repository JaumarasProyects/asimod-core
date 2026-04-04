using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections.Generic;

public class CharacterUI : MonoBehaviour
{
    [Header("References")]
    public CharacterManager characterManager;
    public AsimodClient asimodClient;

    [Header("UI Elements")]
    public TMP_InputField inputField;
    public Button sendButton;
    public TextMeshProUGUI responseText;
    public TextMeshProUGUI statusText;
    public Dropdown characterDropdown;

    [Header("Chat Display")]
    public Transform chatContainer;
    public GameObject messagePrefab;

    private List<CharacterData> characters = new List<CharacterData>();

    private void Start()
    {
        if (characterManager == null)
            characterManager = FindObjectOfType<CharacterManager>();

        if (asimodClient == null)
            asimodClient = FindObjectOfType<AsimodClient>();

        SetupUI();
    }

    private void SetupUI()
    {
        if (sendButton != null)
            sendButton.onClick.AddListener(OnSendClicked);

        if (inputField != null)
            inputField.onSubmit.AddListener(OnInputSubmitted);

        RefreshCharacterList();

        if (characterManager != null)
        {
            characterManager.OnActiveCharacterChanged += OnCharacterChanged;
        }
    }

    public void RefreshCharacterList()
    {
        if (characterDropdown == null || characterManager == null) return;

        characters = characterManager.characters;
        characterDropdown.ClearOptions();

        List<string> options = new List<string>();
        for (int i = 0; i < characters.Count; i++)
        {
            options.Add(characters[i].characterName);
        }

        characterDropdown.AddOptions(options);

        if (characterManager.activeCharacter != null)
        {
            int idx = characters.FindIndex(c => c == characterManager.activeCharacter);
            if (idx >= 0) characterDropdown.value = idx;
        }
    }

    public void OnCharacterDropdownChanged(int index)
    {
        if (characterManager != null && index >= 0 && index < characters.Count)
        {
            characterManager.SetActiveCharacter(characters[index]);
        }
    }

    private void OnCharacterChanged(CharacterData character)
    {
        if (statusText != null)
            statusText.text = $"Active: {character.characterName}";

        RefreshCharacterList();
    }

    private void OnSendClicked()
    {
        SendMessage();
    }

    private void OnInputSubmitted(string text)
    {
        SendMessage();
    }

    private void SendMessage()
    {
        if (asimodClient == null || characterManager == null)
        {
            Debug.LogError("[CharacterUI] Client or Manager is null");
            return;
        }

        string text = inputField.text;
        if (string.IsNullOrEmpty(text)) return;

        if (statusText != null)
            statusText.text = "Sending...";

        asimodClient.SendChatMessage(text, null, (response) =>
        {
            if (statusText != null)
                statusText.text = "Response received";

            if (responseText != null)
                responseText.text = response.response;

            AddMessageToChat("You", text);
            AddMessageToChat(characterManager.GetActiveCharacter().characterName, response.response);

            inputField.text = "";
        }, (error) =>
        {
            if (statusText != null)
                statusText.text = "Error: " + error;
        });
    }

    private void AddMessageToChat(string sender, string message)
    {
        if (chatContainer == null || messagePrefab == null) return;

        GameObject msgObj = Instantiate(messagePrefab, chatContainer);
        TextMeshProUGUI textComp = msgObj.GetComponent<TextMeshProUGUI>();
        if (textComp != null)
        {
            textComp.text = $"{sender}: {message}";
        }
    }
}
