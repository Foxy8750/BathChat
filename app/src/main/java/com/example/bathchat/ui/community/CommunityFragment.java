package com.example.bathchat.ui.community;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

// IMPORTANT: You must import these because they are in a different folder now
import com.example.bathchat.R;
import com.example.bathchat.HeadlineFetcher;
import com.example.bathchat.CourseInfoFetcher;


public class CommunityFragment extends Fragment {

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             ViewGroup container, Bundle savedInstanceState) {
        // Links to your community_board.xml
        return inflater.inflate(R.layout.community_board, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        // 1. Setup the Society Headlines
        LinearLayout headlinesContainer = view.findViewById(R.id.txtSoceityHighlightsList);
        if (headlinesContainer != null) {
            // requireContext() is the safe way to get context in a fragment
            HeadlineFetcher fetcher = new HeadlineFetcher(requireContext(), headlinesContainer);
            fetcher.fetchHeadlines("https://www.thesubath.com");
        }

        // 2. Setup the Course Info AI (formerly mealContainer)
        LinearLayout courseContainer = view.findViewById(R.id.mealContainer);
        if (courseContainer != null) {
            CourseInfoFetcher fetcher2 = new CourseInfoFetcher(requireContext(), courseContainer);
            fetcher2.fetchCourseDetails("Computer Science");
        }
    }
}