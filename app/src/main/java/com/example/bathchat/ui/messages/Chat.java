package com.example.bathchat.ui.messages;

import com.google.gson.annotations.SerializedName;

/**
 * Data model mapped to the backend 'ConnectionRead' schema.
 * This represents a real connection between two users in the database.
 */
public class Chat {
    @SerializedName("match_id")
    private int matchId;

    @SerializedName("user_id")
    private int userId; // The ID of the person you are talking to

    @SerializedName("name")
    private String name;

    @SerializedName("status")
    private String status;

    // This field is for UI display (last message in the list)
    private String lastMessage;

    public Chat(int matchId, int userId, String name, String status) {
        // Assign the parameters to the class-level fields using 'this'
        this.matchId = matchId;
        this.userId = userId;
        this.name = name;
        this.status = status;
    }

    // Getters
    public int getMatchId() { return matchId; }
    public int getUserId() { return userId; }
    public String getName() { return name; }
    public String getStatus() { return status; }
    public String getLastMessage() { return lastMessage; }

    // Setters
    public void setLastMessage(String lastMessage) { this.lastMessage = lastMessage; }
}