package com.example.bathchat;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.recyclerview.widget.RecyclerView;

import java.util.List;

public class ProfileAdapter extends RecyclerView.Adapter<ProfileAdapter.ViewHolder> {

    private List<Profile> profiles;

    public ProfileAdapter(List<Profile> profiles) {
        this.profiles = profiles;
    }

    public static class ViewHolder extends RecyclerView.ViewHolder {
        ImageView imgProfile;
        TextView tvCourse, tvSocieties, tvHobbies;

        public ViewHolder(View itemView) {
            super(itemView);
            imgProfile = itemView.findViewById(R.id.imgProfile);
            tvCourse = itemView.findViewById(R.id.tvCourse);
            tvSocieties = itemView.findViewById(R.id.tvSocieties);
            tvHobbies = itemView.findViewById(R.id.tvHobbies);
        }
    }

    @Override
    public ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_profile_card, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(ViewHolder holder, int position) {
        Profile profile = profiles.get(position);

        holder.imgProfile.setImageResource(profile.imageResId);
        holder.tvCourse.setText(profile.course);
        holder.tvSocieties.setText(profile.societies);
        holder.tvHobbies.setText(profile.hobbies);
    }

    @Override
    public int getItemCount() {
        return profiles.size();
    }
}
