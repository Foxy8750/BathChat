package com.example.bathchat.ui.login;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.example.bathchat.MainActivity;
import com.example.bathchat.databinding.ActivityLoginBinding;
import com.example.bathchat.network.ApiService;
import com.example.bathchat.network.LoginRequest;
import com.example.bathchat.network.LoginResponse;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class LoginActivity extends AppCompatActivity {
    private ActivityLoginBinding binding;
    private static final String TAG = "AUTH_DEBUG";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityLoginBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        // 1. Regular Login Action
        binding.btnLogin.setOnClickListener(v -> {
            String email = binding.etEmail.getText().toString().trim();
            String password = binding.etPassword.getText().toString();
            performLogin(email, password);
        });

        // 2. Navigation to Registration
        binding.btnGoToRegister.setOnClickListener(v -> {
            startActivity(new Intent(this, RegisterActivity.class));
        });

        // 3. Admin Bypass Action (Demo Mode)
        binding.btnAdminBypass.setOnClickListener(v -> {
            Log.d(TAG, "Admin Bypass Triggered");

            // Persist mock data for User #1 to satisfy Fragment dependencies
            saveAuthData("user-admin-bypass", "1");

            startActivity(new Intent(LoginActivity.this, MainActivity.class));
            finish();
        });
    }

    private void performLogin(String email, String password) {
        Retrofit retrofit = new Retrofit.Builder()
                // UPDATE THIS LINE:
                .baseUrl("https://bathchat.onrender.com/")
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        ApiService service = retrofit.create(ApiService.class);
        service.login(new LoginRequest(email, password)).enqueue(new Callback<LoginResponse>() {
            @Override
            public void onResponse(Call<LoginResponse> call, Response<LoginResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    String fullToken = response.body().access_token;
                    // Extract numerical ID from "user-5" format
                    String userId = fullToken.contains("-") ? fullToken.split("-")[1] : "0";

                    saveAuthData(fullToken, userId);
                    startActivity(new Intent(LoginActivity.this, MainActivity.class));
                    finish();
                } else {
                    Toast.makeText(LoginActivity.this, "Login Failed", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<LoginResponse> call, Throwable t) {
                Toast.makeText(LoginActivity.this, "Check Connection", Toast.LENGTH_SHORT).show();
            }
        });
    }

    /**
     * Persists authentication state to SharedPreferences.
     * This is required for the X-User-Id header in subsequent API calls.
     */
    private void saveAuthData(String token, String userId) {
        getSharedPreferences("Auth", MODE_PRIVATE)
                .edit()
                .putString("token", token)
                .putString("user_id", userId)
                .apply();
    }
}