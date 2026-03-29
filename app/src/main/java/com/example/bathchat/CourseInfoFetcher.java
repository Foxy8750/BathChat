package com.example.bathchat;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.LayoutInflater;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.cardview.widget.CardView;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import okhttp3.*;

public class CourseInfoFetcher {
    private static final String API_KEY = "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";
    private static final String API_URL = "https://openrouter.ai/api/v1/chat/completions";

    private final Context context;
    private final LinearLayout container;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public CourseInfoFetcher(Context context, LinearLayout container) {
        this.context = context;
        this.container = container;
    }

    public void fetchCourseDetails(String courseName) {
        executor.execute(() -> {
            try {
                OkHttpClient client = new OkHttpClient();
                String prompt = "Provide 3 short bullet points for a student studying " + courseName + ": 1. Hard module, 2. Career, 3. Tip.";

                JSONObject body = new JSONObject();
                body.put("model", "meta-llama/llama-3.1-8b-instruct:free");
                body.put("messages", new org.json.JSONArray().put(new JSONObject().put("role", "user").put("content", prompt)));

                Request request = new Request.Builder()
                        .url(API_URL)
                        .post(RequestBody.create(body.toString(), MediaType.parse("application/json")))
                        .addHeader("Authorization", "Bearer " + API_KEY)
                        .build();

                Response response = client.newCall(request).execute();
                String resultText = new JSONObject(response.body().string())
                        .getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content");

                mainHandler.post(() -> updateUI(resultText));
            } catch (Exception e) {
                mainHandler.post(() -> updateUI("Could not load course info."));
            }
        });
    }

    private void updateUI(String info) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(context);
        CardView card = (CardView) inflater.inflate(R.layout.card_headline, container, false);
        ((TextView) card.findViewById(R.id.txtHeadline)).setText(info);
        container.addView(card);
    }
}