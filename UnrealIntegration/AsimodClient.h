#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Http.h"
#include "AsimodClient.generated.h"

// --- Unreal Structures for JSON ---

USTRUCT(BlueprintType)
struct FAsimodChatResponse
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    FString Response;

    UPROPERTY(BlueprintReadOnly)
    FString CleanText;

    UPROPERTY(BlueprintReadOnly)
    TArray<FString> Emojis;

    UPROPERTY(BlueprintReadOnly)
    FString Status;
};

// --- Delegates for Blueprints ---
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FAsimodChatDelegate, FAsimodChatResponse, Response);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FAsimodErrorDelegate, FString, ErrorMessage);

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class ASIMOD_API UAsimodClient : public UActorComponent
{
    GENERATED_BODY()

public:    
    UAsimodClient();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Asimod")
    FString ApiBaseUrl = "http://localhost:8000/v1";

    // --- Public Blueprint Functions ---

    UFUNCTION(BlueprintCallable, Category = "Asimod")
    void SendChatMessage(FString Text, FString Model = "");

    UFUNCTION(BlueprintCallable, Category = "Asimod")
    void StopAudio();

    UFUNCTION(BlueprintCallable, Category = "Asimod")
    void ToggleMicrophone(bool bEnabled);

    // --- Callbacks ---

    UPROPERTY(BlueprintAssignable, Category = "Asimod")
    FAsimodChatDelegate OnChatReceived;

    UPROPERTY(BlueprintAssignable, Category = "Asimod")
    FAsimodErrorDelegate OnRequestError;

protected:
    void OnChatResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);
};
