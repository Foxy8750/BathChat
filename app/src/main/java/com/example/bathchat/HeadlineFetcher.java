package com.example.bathchat;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.cardview.widget.CardView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class HeadlineFetcher {

    private static final String API_KEY = "YOUR_ANTHROPIC_API_KEY";
    private static final String API_URL = "https://api.anthropic.com/v1/messages";

    private final Context context;
    private final LinearLayout container;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public HeadlineFetcher(Context context, LinearLayout container) {
        this.context = context;
        this.container = container;
    }

    public void fetchHeadlines(String websiteUrl) {
        executor.execute(() -> {
            try {
                OkHttpClient client = new OkHttpClient();

                // Build the prompt
                String prompt = "Please visit this website: " + websiteUrl +
                        " and generate exactly 3 to 5 short punchy headlines summarising " +
                        "the main stories or content on the page. " +
                        "Reply ONLY with a JSON array of strings, no extra text. " +
                        "Example: [\"Headline one\", \"Headline two\", \"Headline three\"]";

                // Build request body
                JSONObject message = new JSONObject();
                message.put("role", "user");
                message.put("content", prompt);

                JSONArray messages = new JSONArray();
                messages.put(message);

                // Add web search tool
                JSONObject webSearchTool = new JSONObject();
                webSearchTool.put("type", "web_search_20250305");
                webSearchTool.put("name", "web_search");

                JSONArray tools = new JSONArray();
                tools.put(webSearchTool);

                JSONObject body = new JSONObject();
                body.put("model", "claude-sonnet-4-20250514");
                body.put("max_tokens", 1000);
                body.put("messages", messages);
                body.put("tools", tools);

                RequestBody requestBody = RequestBody.create(
                        body.toString(),
                        MediaType.parse("application/json")
                );

                Request request = new Request.Builder()
                        .url(API_URL)
                        .post(requestBody)
                        .addHeader("Content-Type", "application/json")
                        .addHeader("x-api-key", API_KEY)
                        .addHeader("anthropic-version", "2023-06-01")
                        .build();

                Response response = client.newCall(request).execute();
                String responseBody = response.body().string();

                // Parse response
                JSONObject json = new JSONObject(responseBody);
                JSONArray content = json.getJSONArray("content");

                // Find the text block in response
                String resultText = "";
                for (int i = 0; i < content.length(); i++) {
                    JSONObject block = content.getJSONObject(i);
                    if (block.getString("type").equals("text")) {
                        resultText = block.getString("text");
                        break;
                    }
                }

                // Parse headlines from JSON array
                // Strip any accidental markdown backticks
                resultText = resultText.replace("```json", "").replace("```", "").trim();
                JSONArray headlinesArray = new JSONArray(resultText);

                List<String> headlines = new ArrayList<>();
                for (int i = 0; i < headlinesArray.length(); i++) {
                    headlines.add(headlinesArray.getString(i));
                }

                // Update UI on main thread
                mainHandler.post(() -> populateCards(headlines));

            } catch (Exception e) {
                e.printStackTrace();
                mainHandler.post(() -> {
                    // Show error card if something goes wrong
                    addErrorCard("Failed to load headlines: " + e.getMessage());
                });
            }
        });
    }

    private void populateCards(List<String> headlines) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(context);

        for (String headline : headlines) {
            CardView card = (CardView) inflater.inflate(
                    R.layout.card_headline, container, false);
            TextView txt = card.findViewById(R.id.txtHeadline);
            txt.setText(headline);
            container.addView(card);
        }
    }

    private void addErrorCard(String message) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(context);
        CardView card = (CardView) inflater.inflate(
                R.layout.card_headline, container, false);
        TextView txt = card.findViewById(R.id.txtHeadline);
        txt.setText(message);
        txt.setTextColor(0xFFCC0000);
        container.addView(card);
    }
}
