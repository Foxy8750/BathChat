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
import androidx.recyclerview.widget.LinearLayoutManager;
import com.example.bathchat.databinding.FragmentChatDetailBinding;
import com.example.bathchat.network.ApiService;
import java.util.ArrayList;
import java.util.List;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ChatDetailFragment extends Fragment {
    private FragmentChatDetailBinding binding;
    private MessageAdapter adapter;
    private List<ChatMessage> messageList = new ArrayList<>();
    private int otherUserId;
    private String myId;

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        binding = FragmentChatDetailBinding.inflate(inflater, container, false);
        return binding.getRoot();
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        otherUserId = getArguments().getInt("other_user_id");
        myId = requireActivity().getSharedPreferences("Auth", Context.MODE_PRIVATE).getString("user_id", "1");

        adapter = new MessageAdapter(messageList, Integer.parseInt(myId));
        binding.rvMessages.setLayoutManager(new LinearLayoutManager(getContext()));
        binding.rvMessages.setAdapter(adapter);

        fetchHistory();

        binding.btnSend.setOnClickListener(v -> {
            String text = binding.etMessage.getText().toString().trim();
            if (!text.isEmpty()) sendMessage(text);
        });
    }

    private void fetchHistory() {
        Retrofit retrofit = new Retrofit.Builder().baseUrl("https://bathchat.onrender.com/").addConverterFactory(GsonConverterFactory.create()).build();
        ApiService service = retrofit.create(ApiService.class);
        service.getChatHistory(myId, otherUserId).enqueue(new Callback<List<ChatMessage>>() {
            @Override
            public void onResponse(Call<List<ChatMessage>> call, Response<List<ChatMessage>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    messageList.clear();
                    messageList.addAll(response.body());
                    adapter.notifyDataSetChanged();
                    binding.rvMessages.scrollToPosition(messageList.size() - 1);
                }
            }
            @Override
            public void onFailure(Call<List<ChatMessage>> call, Throwable t) {}
        });
    }

    private void sendMessage(String text) {
        Retrofit retrofit = new Retrofit.Builder().baseUrl("https://bathchat.onrender.com/").addConverterFactory(GsonConverterFactory.create()).build();
        ApiService service = retrofit.create(ApiService.class);
        service.sendMessage(myId, otherUserId, new ChatMessageCreate(text)).enqueue(new Callback<ChatMessage>() {
            @Override
            public void onResponse(Call<ChatMessage> call, Response<ChatMessage> response) {
                if (response.isSuccessful()) {
                    messageList.add(response.body());
                    adapter.notifyItemInserted(messageList.size() - 1);
                    binding.etMessage.setText("");
                    binding.rvMessages.smoothScrollToPosition(messageList.size() - 1);
                }
            }
            @Override
            public void onFailure(Call<ChatMessage> call, Throwable t) {}
        });
    }
}