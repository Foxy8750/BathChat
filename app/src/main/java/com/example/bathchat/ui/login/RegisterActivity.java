package com.example.bathchat.ui.login;

import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.example.bathchat.databinding.ActivityRegisterBinding;
import com.example.bathchat.network.ApiService;
import com.example.bathchat.network.RegisterRequest;
import com.example.bathchat.network.RegisterResponse;
import java.util.concurrent.TimeUnit;
import okhttp3.OkHttpClient;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class RegisterActivity extends AppCompatActivity {
    private ActivityRegisterBinding binding;
    private static final String TAG = "REG_DEBUG";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityRegisterBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        binding.btnRegister.setOnClickListener(v -> {
            String name = binding.etName.getText().toString().trim();
            String email = binding.etEmail.getText().toString().trim().toLowerCase();
            String password = binding.etPassword.getText().toString();

            // Basic validation before hitting the network
            if (name.isEmpty() || !email.endsWith("@bath.ac.uk") || password.length() < 6) {
                Toast.makeText(this, "Check your details! (Email must be @bath.ac.uk)", Toast.LENGTH_SHORT).show();
                return;
            }

            performRegistration(name, email, password);
        });
    }

    private void performRegistration(String name, String email, String password) {
        // Build a custom client to handle Render's slow "Cold Starts"
        OkHttpClient okHttpClient = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl("https://bathchat.onrender.com/")
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        ApiService service = retrofit.create(ApiService.class);
        RegisterRequest request = new RegisterRequest(name, email, password);

        service.register(request).enqueue(new Callback<RegisterResponse>() {
            @Override
            public void onResponse(Call<RegisterResponse> call, Response<RegisterResponse> response) {
                if (response.isSuccessful()) {
                    Toast.makeText(RegisterActivity.this, "Success! Please Login.", Toast.LENGTH_LONG).show();
                    finish(); // Closes registration and goes back to LoginActivity
                } else {
                    // This usually triggers if the email already exists (Error 400)
                    Log.e(TAG, "Error Code: " + response.code());
                    Toast.makeText(RegisterActivity.this, "Registration Failed: User might already exist.", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<RegisterResponse> call, Throwable t) {
                Log.e(TAG, "Network Failure: " + t.getMessage());
                Toast.makeText(RegisterActivity.this, "Network Error - Try again in a moment.", Toast.LENGTH_SHORT).show();
            }
        });
    }
}