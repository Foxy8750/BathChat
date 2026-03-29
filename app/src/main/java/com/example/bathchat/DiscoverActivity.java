package com.example.bathchat;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.PagerSnapHelper;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONObject;
import org.json.JSONException;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class DiscoverActivity extends AppCompatActivity {

    private RecyclerView recyclerView;
    private ProfileAdapter adapter;
    private List<Profile> profileList;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final OkHttpClient client = new OkHttpClient();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.discover);

        recyclerView = findViewById(R.id.recyclerProfiles);
        recyclerView.setLayoutManager(new LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false));

        // 1. Initialize with placeholder profiles
        profileList = new ArrayList<>();
        profileList.add(new Profile(R.drawable.ic_home_black_24dp));
        profileList.add(new Profile(R.drawable.ic_home_black_24dp));
        profileList.add(new Profile(R.drawable.ic_home_black_24dp));

        adapter = new ProfileAdapter(profileList);
        recyclerView.setAdapter(adapter);

        // 2. Add SnapHelper for that "Tinder/swipe" feel
        if (recyclerView.getOnFlingListener() == null) {
            PagerSnapHelper snapHelper = new PagerSnapHelper();
            snapHelper.attachToRecyclerView(recyclerView);
        }

        // 3. Load data for all profiles (or just the first one to start)
        // Replace "12345" with your actual logged-in user's ID
        for (int i = 0; i < profileList.size(); i++) {
            loadMatchData("12345", profileList.get(i), i);
        }
    }

    public void loadMatchData(String userId, Profile profile, int position) {
        // NOTE: 10.0.2.2 is how the Android Emulator accesses your computer's localhost
        String url = "https://bathchat.onrender.com/discovery/matches?userId=" + userId;

        Request request = new Request.Builder()
                .url(url)
                .build();

        executor.execute(() -> {
            try (Response response = client.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    String responseData = response.body().string();
                    JSONObject json = new JSONObject(responseData);

                    // Map JSON response to your specific fields
                    String score = json.optString("match_score", "N/A");
                    String reason = json.optString("reason", "No reason provided.");
                    String icebreaker = json.optString("icebreaker", "Say hello!");
                    String status = json.optString("status", "Active");

                    // Update UI on main thread
                    mainHandler.post(() -> {
                        profile.updateFromApi(score, reason, icebreaker, status);
                        adapter.notifyItemChanged(position);
                    });
                }
            } catch (IOException | JSONException e) {
                e.printStackTrace();
                mainHandler.post(() -> {
                    profile.updateFromApi("Error", "Could not connect to server", "", "");
                    adapter.notifyItemChanged(position);
                });
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}