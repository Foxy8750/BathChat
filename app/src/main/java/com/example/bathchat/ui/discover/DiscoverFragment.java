package com.example.bathchat.ui.discover;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import androidx.annotation.NonNull;
import androidx.fragment.app.Fragment;
import com.example.bathchat.R;

public class DiscoverFragment extends Fragment {
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        // Ensure R.layout.discover exists in your res/layout folder!
        return inflater.inflate(R.layout.discover, container, false);
    }
}