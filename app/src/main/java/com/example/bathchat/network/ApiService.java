// app/src/main/java/com/example/bathchat/network/ApiService.java
package com.example.bathchat.network;

import com.example.bathchat.ui.messages.Chat;
import com.example.bathchat.ui.messages.ChatMessage;
import com.example.bathchat.ui.messages.ChatMessageCreate;
import java.util.List;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.Header;
import retrofit2.http.POST;
import retrofit2.http.Path;

public interface ApiService {
    @POST("/auth/login")
    Call<LoginResponse> login(@Body LoginRequest request);

    @POST("/auth/register")
    Call<RegisterResponse> register(@Body RegisterRequest request);

    @GET("/connections")
    Call<List<Chat>> getConnections(@Header("X-User-Id") String userId);

    // Fetch previous messages for this specific connection
    @GET("/connections/{connection_user_id}/chat")
    Call<List<ChatMessage>> getChatHistory(
            @Header("X-User-Id") String userId,
            @Path("connection_user_id") int otherUserId
    );

    @POST("/connections/{connection_user_id}/chat")
    Call<ChatMessage> sendMessage(
            @Header("X-User-Id") String userId,
            @Path("connection_user_id") int otherUserId,
            @Body ChatMessageCreate request
    );
}