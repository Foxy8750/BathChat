package com.example.bathchat;

public class Profile {
    // These must be public so the Adapter can see them
    public String matchScore = "Loading...";
    public String aiReason = "";
    public String aiIcebreaker = "";
    public String status = "";
    public int imageResId;

    // Constructor
    public Profile(int imageResId) {
        this.imageResId = imageResId;
    }

    // THIS IS THE METHOD THE ACTIVITY IS LOOKING FOR
    public void updateFromApi(String score, String reason, String icebreaker, String status) {
        this.matchScore = score;
        this.aiReason = reason;
        this.aiIcebreaker = icebreaker;
        this.status = status;
    }
}