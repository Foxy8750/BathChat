package com.example.bathchat.ui.discover;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.PagerSnapHelper;
import androidx.recyclerview.widget.RecyclerView;

import com.example.bathchat.Profile;
import com.example.bathchat.ProfileAdapter;
import com.example.bathchat.R;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class DiscoverFragment extends Fragment {

    private RecyclerView recyclerView;
    private ProfileAdapter adapter;
    private List<Profile> profileList;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final OkHttpClient client = new OkHttpClient();

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        return inflater.inflate(R.layout.discover, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        recyclerView = view.findViewById(R.id.recyclerProfiles); // [cite: 32]
        recyclerView.setLayoutManager(new LinearLayoutManager(requireContext(), LinearLayoutManager.HORIZONTAL, false));

        profileList = new ArrayList<>();
        adapter = new ProfileAdapter(profileList); // [cite: 27]
        recyclerView.setAdapter(adapter);

        PagerSnapHelper snapHelper = new PagerSnapHelper();
        snapHelper.attachToRecyclerView(recyclerView); // [cite: 34]

        // 1. Get the REAL user ID saved during Login or Admin Bypass [cite: 55]
        String userId = requireContext().getSharedPreferences("Auth", android.content.Context.MODE_PRIVATE)
                .getString("user_id", "1");

        // 2. Fetch the entire list of matches once
        fetchDiscoveryMatches(userId);
    }

    public void fetchDiscoveryMatches(String userId) {
        // The backend identifies the user via the Header, not the URL
        String url = "https://bathchat.onrender.com/discovery/matches";

        Request request = new Request.Builder()
                .url(url)
                .addHeader("X-User-Id", userId) // CRITICAL: This allows the AI to find unique matches
                .build();

        executor.execute(() -> { // [cite: 29]
            try (Response response = client.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    String responseData = response.body().string();

                    // 3. Parse as a JSONArray (the list of 3 matches shown in your screenshot)
                    org.json.JSONArray jsonArray = new org.json.JSONArray(responseData);

                    mainHandler.post(() -> {
                        profileList.clear(); // Remove dummy data
                        for (int i = 0; i < jsonArray.length(); i++) {
                            try {
                                org.json.JSONObject json = jsonArray.getJSONObject(i);

                                // Create a new unique profile for each match
                                Profile p = new Profile(R.drawable.ic_home_black_24dp); // [cite: 183]

                                // Map the backend JSON keys to your Profile object
                                p.updateFromApi(
                                        String.format("%.1f", json.optDouble("match_score", 0.0)),
                                        json.optString("ai_reason", "N/A"),
                                        json.optString("ai_icebreaker", "Say hello!"),
                                        json.optString("status", "suggested")
                                );
                                profileList.add(p);
                            } catch (org.json.JSONException e) {
                                e.printStackTrace();
                            }
                        }
                        adapter.notifyDataSetChanged(); // Refresh the UI with all 3 unique cards
                    });
                }
            } catch (java.io.IOException | org.json.JSONException e) {
                e.printStackTrace();
            }
        });
    }
}