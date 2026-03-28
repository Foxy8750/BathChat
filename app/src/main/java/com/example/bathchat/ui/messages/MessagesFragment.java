package com.example.bathchat.ui.messages;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import androidx.annotation.NonNull;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.example.bathchat.R;
import java.util.ArrayList;
import java.util.List;

public class MessagesFragment extends Fragment {

    private RecyclerView recyclerView;
    private ChatAdapter chatAdapter;
    private List<Chat> chatList;

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             ViewGroup container, Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.messages, container, false);

        recyclerView = root.findViewById(R.id.rv_chats);
        recyclerView.setLayoutManager(new LinearLayoutManager(getContext()));

        // Initialize friends list with the required 3-argument constructor
        chatList = new ArrayList<>();
        chatList.add(new Chat("Matt", "", "")); // No message = "Select To Type!"
        chatList.add(new Chat("Mandeep", "Yo! Let's hit the SU tonight.", "read"));
        chatList.add(new Chat("David", "", ""));
        chatList.add(new Chat("Andy", "Ready for the 24-hour build?", "delivered"));

        chatAdapter = new ChatAdapter(chatList, chat -> {
            // This code runs when you click a chat item
            android.widget.Toast.makeText(getContext(),
                    "Opening chat with " + chat.getName() + "... (Backend offline)",
                    android.widget.Toast.LENGTH_SHORT).show();

            // Logic Engine Tip: For the demo, you could navigate to a
            // static "ChatDetailFragment" here to show what a convo looks like.
        });
        recyclerView.setAdapter(chatAdapter);

        return root;
    }
}