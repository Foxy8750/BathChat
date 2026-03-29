package com.example.bathchat.ui.messages;

/**
 * Data model for a single chat thread in the SocialMatch AI platform.
 */
public class Chat {
    private String name;
    private String lastMessage;
    private String status; // Options: "sent", "delivered", "read", or ""

    public Chat(String name, String lastMessage, String status) {
        this.name = name;
        this.lastMessage = lastMessage;
        this.status = status;
    }

    public String getName() { return name; }
    public String getLastMessage() { return lastMessage; }
    public String getStatus() { return status; }
}