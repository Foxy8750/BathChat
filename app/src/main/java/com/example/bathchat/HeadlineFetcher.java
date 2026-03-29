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
import okhttp3.*;

public class HeadlineFetcher {
    private static final String API_KEY = "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";
    private static final String API_URL = "https://openrouter.ai/api/v1/chat/completions";

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
                String prompt = "Give me a JSON array of 3 headlines for " + websiteUrl + ". ONLY return the array like [\"A\", \"B\", \"C\"]";

                JSONObject body = new JSONObject();
                body.put("model", "meta-llama/llama-3.1-8b-instruct:free");
                body.put("messages", new JSONArray().put(new JSONObject().put("role", "user").put("content", prompt)));

                Request request = new Request.Builder()
                        .url(API_URL)
                        .post(RequestBody.create(body.toString(), MediaType.parse("application/json")))
                        .addHeader("Authorization", "Bearer " + API_KEY)
                        .build();

                Response response = client.newCall(request).execute();
                String resultText = new JSONObject(response.body().string())
                        .getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content");

                JSONArray array = new JSONArray(resultText.replace("```json", "").replace("```", "").trim());
                List<String> headlines = new ArrayList<>();
                for (int i = 0; i < array.length(); i++) headlines.add(array.getString(i));

                mainHandler.post(() -> populateCards(headlines));
            } catch (Exception e) {
                mainHandler.post(() -> addErrorCard("Failed to load headlines."));
            }
        });
    }

    private void populateCards(List<String> headlines) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(context);
        for (String headline : headlines) {
            CardView card = (CardView) inflater.inflate(R.layout.card_headline, container, false);
            ((TextView) card.findViewById(R.id.txtHeadline)).setText(headline);
            container.addView(card);
        }
    }

    private void addErrorCard(String msg) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(context);
        CardView card = (CardView) inflater.inflate(R.layout.card_headline, container, false);
        TextView tv = card.findViewById(R.id.txtHeadline);
        tv.setText(msg);
        tv.setTextColor(0xFFCC0000);
        container.addView(card);
    }
}