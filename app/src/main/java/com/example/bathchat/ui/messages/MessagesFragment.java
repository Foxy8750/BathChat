package com.example.bathchat.ui.messages;

import android.content.Context;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Toast;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.navigation.Navigation;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.bathchat.R;
import com.example.bathchat.network.ApiService;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class MessagesFragment extends Fragment {

    private RecyclerView recyclerView;
    private ChatAdapter chatAdapter;
    private List<Chat> chatList = new ArrayList<>();

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        // Links to the messages.xml layout
        return inflater.inflate(R.layout.messages, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        // Standard ID lookup
        recyclerView = view.findViewById(R.id.rv_chats);
        recyclerView.setLayoutManager(new LinearLayoutManager(getContext()));

        // Setup the adapter with the navigation logic
        chatAdapter = new ChatAdapter(chatList, chat -> {
            Bundle bundle = new Bundle();
            bundle.putInt("other_user_id", chat.getUserId());
            bundle.putString("other_user_name", chat.getName());

            // Navigate to the Chat Detail screen
            Navigation.findNavController(view)
                    .navigate(R.id.action_navigation_messages_to_chatDetail, bundle);
        });

        recyclerView.setAdapter(chatAdapter);

        // Fetch the REAL connections from your database
        loadConnectionsFromDb();
    }

    private void loadConnectionsFromDb() {
        // Retrieve the authenticated user ID saved during Login/Admin Bypass
        String userId = requireActivity().getSharedPreferences("Auth", Context.MODE_PRIVATE)
                .getString("user_id", "1");

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl("https://bathchat.onrender.com/")
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        ApiService service = retrofit.create(ApiService.class);

        // Authenticated call to get your active connections
        service.getConnections(userId).enqueue(new Callback<List<Chat>>() {
            @Override
            public void onResponse(Call<List<Chat>> call, Response<List<Chat>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    chatList.clear();
                    chatList.addAll(response.body());
                    chatAdapter.notifyDataSetChanged();
                } else if (chatList.isEmpty()) {
                    Toast.makeText(getContext(), "Go to Discover to find connections!", Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<List<Chat>> call, Throwable t) {
                Toast.makeText(getContext(), "Database Offline - Try again later", Toast.LENGTH_SHORT).show();
            }
        });
    }
}