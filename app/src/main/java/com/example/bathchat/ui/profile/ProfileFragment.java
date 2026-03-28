package com.example.bathchat.ui.profile;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.fragment.app.Fragment;
import androidx.navigation.Navigation;
import com.example.bathchat.R;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public class ProfileFragment extends Fragment {

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.profile, container, false);

        // 1. Load data from JSON
        loadProfileData(root);

        // 2. Setup Settings Button Click
        root.findViewById(R.id.btn_settings).setOnClickListener(v -> {
            Navigation.findNavController(v).navigate(R.id.navigation_settings);
        });

        return root;
    }

    private void loadProfileData(View root) {
        try {
            InputStream is = requireContext().getAssets().open("profile_dummy.json");
            int size = is.available();
            byte[] buffer = new byte[size];
            is.read(buffer);
            is.close();
            String json = new String(buffer, StandardCharsets.UTF_8);

            JSONObject obj = new JSONObject(json);
            ((TextView) root.findViewById(R.id.tv_elo)).setText(String.valueOf(obj.getInt("elo_score")));
            ((TextView) root.findViewById(R.id.tv_tier)).setText(obj.getString("badge_tier"));
            ((TextView) root.findViewById(R.id.tv_course)).setText(obj.getString("course"));
            ((TextView) root.findViewById(R.id.tv_bio)).setText(obj.getString("bio"));

            JSONArray societies = obj.getJSONArray("societies");
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < societies.length(); i++) {
                sb.append(societies.getString(i)).append(i == societies.length() - 1 ? "" : ", ");
            }
            ((TextView) root.findViewById(R.id.tv_societies)).setText(sb.toString());

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}