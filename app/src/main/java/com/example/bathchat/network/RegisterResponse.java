package com.example.bathchat.network;

import com.google.gson.annotations.SerializedName;

public class RegisterResponse {

    @SerializedName("id")
    public int id;

    @SerializedName("email")
    public String email;

    // This ensures that if the backend sends "full_name", your app still reads it correctly.
    @SerializedName("name")
    public String name;

    /* Optional: If your backend sends a token or message on registration,
    you would add them here like this:

    @SerializedName("message")
    public String message;
    */
}