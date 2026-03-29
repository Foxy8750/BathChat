package com.example.bathchat.ui.messages;

public class ChatMessageCreate {
    public String content;
    public String message_type = "text";

    public ChatMessageCreate(String content) {
        this.content = content;
    }
}