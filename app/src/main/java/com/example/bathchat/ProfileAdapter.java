package com.example.bathchat;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import java.util.List;

public class ProfileAdapter extends RecyclerView.Adapter<ProfileAdapter.ViewHolder> {

    private List<Profile> profiles;

    public ProfileAdapter(List<Profile> profiles) {
        this.profiles = profiles;
    }

    public static class ViewHolder extends RecyclerView.ViewHolder {
        ImageView imgProfile;
        TextView tvMatchScore, tvAiReason, tvAiIcebreaker, tvStatus;

        public ViewHolder(View itemView) {
            super(itemView);
            imgProfile = itemView.findViewById(R.id.imgProfile);
            // Updated IDs to match your intent
            tvMatchScore = itemView.findViewById(R.id.match_score);
            tvAiReason = itemView.findViewById(R.id.ai_reason);
            tvAiIcebreaker = itemView.findViewById(R.id.ai_icebreaker);
            tvStatus = itemView.findViewById(R.id.status);
        }
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_profile_card, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        Profile profile = profiles.get(position);

        holder.imgProfile.setImageResource(profile.imageResId);

        // Setting the API data
        holder.tvMatchScore.setText(profile.matchScore);
        holder.tvAiReason.setText(profile.aiReason);
        holder.tvAiIcebreaker.setText(profile.aiIcebreaker);
        holder.tvStatus.setText(profile.status);
    }

    @Override
    public int getItemCount() {
        return (profiles != null) ? profiles.size() : 0;
    }
}