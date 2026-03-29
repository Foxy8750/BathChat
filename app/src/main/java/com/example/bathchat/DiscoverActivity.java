package com.example.bathchat;

import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.PagerSnapHelper;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

public class DiscoverActivity extends AppCompatActivity {

    RecyclerView recyclerView;
    ProfileAdapter adapter;
    List<Profile> profileList;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.discover);

        recyclerView = findViewById(R.id.recyclerProfiles);

        // Horizontal layout
        LinearLayoutManager layoutManager =
                new LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false);
        recyclerView.setLayoutManager(layoutManager);

        // Dummy data (replace later)
        profileList = new ArrayList<>();
        profileList.add(new Profile(
                R.drawable.ic_home_black_24dp,
                "Computer Science",
                "AI Society, Basketball",
                "Gym, Coding, Music"
        ));
        profileList.add(new Profile(
                R.drawable.ic_home_black_24dp,
                "Economics",
                "Finance Society",
                "Trading, Travel"
        ));
        profileList.add(new Profile(
                R.drawable.ic_home_black_24dp,
                "Architecture",
                "Design Society",
                "Sketching, Photography"
        ));

        adapter = new ProfileAdapter(profileList);
        recyclerView.setAdapter(adapter);

        // 🔥 Snap to one card at a time (like ViewPager)
        PagerSnapHelper snapHelper = new PagerSnapHelper();
        snapHelper.attachToRecyclerView(recyclerView);
    }
}
