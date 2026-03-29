package com.example.bathchat.ui.messages;

import com.google.gson.annotations.SerializedName;

public class ChatMessage {
    public int id;
    @SerializedName("sender_id")
    public int senderId;
    public String content;
    @SerializedName("message_type")
    public String messageType;
    @SerializedName("sent_at")
    public String sentAt;
}