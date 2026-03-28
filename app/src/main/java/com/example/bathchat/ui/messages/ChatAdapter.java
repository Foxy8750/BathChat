package com.example.bathchat.ui.messages;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import com.example.bathchat.R;
import java.util.List;

public class ChatAdapter extends RecyclerView.Adapter<ChatAdapter.ViewHolder> {

    private List<Chat> chatList;
    private OnChatClickListener listener; // New listener variable

    // Define the interface for the click action
    public interface OnChatClickListener {
        void onChatClick(Chat chat);
    }

    // Updated constructor to include the listener
    public ChatAdapter(List<Chat> chatList, OnChatClickListener listener) {
        this.chatList = chatList;
        this.listener = listener;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_chat, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        Chat chat = chatList.get(position);
        holder.name.setText(chat.getName());

        if (chat.getLastMessage() == null || chat.getLastMessage().isEmpty()) {
            holder.lastMessage.setText("Select To Type!");
            holder.statusTick.setVisibility(View.GONE);
        } else {
            holder.lastMessage.setText(chat.getLastMessage());
            holder.statusTick.setVisibility(View.VISIBLE);
            applyStatusStyle(holder.statusTick, chat.getStatus());
        }

        // Set the click listener on the entire row
        holder.itemView.setOnClickListener(v -> {
            if (listener != null) {
                listener.onChatClick(chat);
            }
        });
    }

    private void applyStatusStyle(ImageView imageView, String status) {
        if ("read".equals(status)) {
            imageView.setColorFilter(0xFF34B7F1);
        } else {
            imageView.setColorFilter(0xFF888888);
        }
    }

    @Override
    public int getItemCount() {
        return chatList.size();
    }

    public static class ViewHolder extends RecyclerView.ViewHolder {
        TextView name, lastMessage;
        ImageView statusTick;

        public ViewHolder(View itemView) {
            super(itemView);
            name = itemView.findViewById(R.id.chat_name);
            lastMessage = itemView.findViewById(R.id.chat_last_message);
            statusTick = itemView.findViewById(R.id.chat_status);
        }
    }
}