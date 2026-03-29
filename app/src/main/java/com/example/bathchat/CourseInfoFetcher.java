package com.example.bathchat;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.cardview.widget.CardView;
import android.view.LayoutInflater;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class CourseInfoFetcher {

    private static final String API_KEY = "YOUR_ANTHROPIC_API_KEY";
    private static final String API_URL = "https://api.anthropic.com/v1/messages";

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

                // Build a specific prompt for course info
                String prompt = "The user is studying " + courseName + " at university. " +
                        "Provide 3 short, helpful bullet points about this course: " +
                        "1. A common difficult module to watch out for. " +
                        "2. A top career path. " +
                        "3. A pro study tip for this specific field. " +
                        "Keep each point under 15 words.";

                JSONObject body = new JSONObject();
                body.put("model", "claude-3-sonnet-20240229"); // Use a stable model name
                body.put("max_tokens", 500);

                JSONArray messages = new JSONArray();
                JSONObject msg = new JSONObject();
                msg.put("role", "user");
                msg.put("content", prompt);
                messages.put(msg);

                body.put("messages", messages);

                RequestBody requestBody = RequestBody.create(
                        body.toString(),
                        MediaType.get("application/json; charset=utf-8")
                );

                Request request = new Request.Builder()
                        .url(API_URL)
                        .post(requestBody)
                        .addHeader("x-api-key", API_KEY)
                        .addHeader("anthropic-version", "2023-06-01")
                        .build();

                Response response = client.newCall(request).execute();
                String responseBody = response.body().string();

                // Extract text from Claude's response
                JSONObject jsonResponse = new JSONObject(responseBody);
                String aiText = jsonResponse.getJSONArray("content")
                        .getJSONObject(0)
                        .getString("text");

                mainHandler.post(() -> updateUI(aiText));

            } catch (Exception e) {
                e.printStackTrace();
                mainHandler.post(() -> updateUI("Could not load course info."));
            }
        });
    }

    private void updateUI(String info) {
        container.removeAllViews();

        // Use your existing card layout
        LayoutInflater inflater = LayoutInflater.from(context);
        CardView card = (CardView) inflater.inflate(R.layout.card_headline, container, false);

        TextView txt = card.findViewById(R.id.txtHeadline);
        txt.setText(info);

        container.addView(card);
    }
}