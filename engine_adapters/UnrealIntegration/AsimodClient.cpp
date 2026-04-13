#include "AsimodClient.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

UAsimodClient::UAsimodClient()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UAsimodClient::SendChatMessage(FString Text, FString Model)
{
    FHttpModule* Http = &FHttpModule::Get();
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = Http->CreateRequest();

    Request->OnProcessRequestComplete().BindUObject(this, &UAsimodClient::OnChatResponseReceived);
    Request->SetURL(ApiBaseUrl + "/chat");
    Request->SetVerb("POST");
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
    JsonObject->SetStringField("text", Text);
    if (!Model.IsEmpty()) JsonObject->SetStringField("model", Model);

    FString RequestPayload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RequestPayload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

    Request->SetContentAsString(RequestPayload);
    Request->ProcessRequest();
}

void UAsimodClient::OnChatResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    if (bWasSuccessful && Response.IsValid())
    {
        TSharedPtr<FJsonObject> JsonObject;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());

        if (FJsonSerializer::Deserialize(Reader, JsonObject))
        {
            FAsimodChatResponse ChatResponse;
            ChatResponse.Response = JsonObject->GetStringField("response");
            ChatResponse.CleanText = JsonObject->GetStringField("clean_text");
            ChatResponse.Status = JsonObject->GetStringField("status");

            TArray<TSharedPtr<FJsonValue>> EmojiArray = JsonObject->GetArrayField("emojis");
            for (auto EmojiValue : EmojiArray)
            {
                ChatResponse.Emojis.Add(EmojiValue->AsString());
            }

            OnChatReceived.Broadcast(ChatResponse);
            return;
        }
    }
    OnRequestError.Broadcast(TEXT("HTTP Request Failed"));
}

void UAsimodClient::StopAudio()
{
    FHttpModule* Http = &FHttpModule::Get();
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = Http->CreateRequest();
    Request->SetURL(ApiBaseUrl + "/audio/stop");
    Request->SetVerb("POST");
    Request->ProcessRequest();
}

void UAsimodClient::ToggleMicrophone(bool bEnabled)
{
    FHttpModule* Http = &FHttpModule::Get();
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = Http->CreateRequest();
    Request->SetURL(ApiBaseUrl + "/config");
    Request->SetVerb("POST");
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    FString Body = bEnabled ? TEXT("{\"stt_mode\": \"micro\"}") : TEXT("{\"stt_mode\": \"none\"}");
    Request->SetContentAsString(Body);
    Request->ProcessRequest();
}
