package com.example.bathchat;

import android.os.Bundle;
import com.google.android.material.bottomnavigation.BottomNavigationView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.navigation.NavController;
import androidx.navigation.Navigation;
import androidx.navigation.ui.AppBarConfiguration;
import androidx.navigation.ui.NavigationUI;
import com.example.bathchat.databinding.ActivityMainBinding;

public class MainActivity extends AppCompatActivity {
    private ActivityMainBinding binding;
    // 1. Move NavController to a class-level variable
    private NavController navController;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        // These IDs are "Top Level"—they will NOT show a back arrow
        AppBarConfiguration appBarConfiguration = new AppBarConfiguration.Builder(
                R.id.navigation_discover,
                R.id.navigation_messages,
                R.id.navigation_community,
                R.id.navigation_profile)
                .build();

        // 2. Initialize the class-level navController
        navController = Navigation.findNavController(this, R.id.nav_host_fragment_activity_main);

        NavigationUI.setupActionBarWithNavController(this, navController, appBarConfiguration);
        NavigationUI.setupWithNavController(binding.navView, navController);
    }

    // 3. ADD THIS METHOD: This captures the click on the "Up" arrow
    @Override
    public boolean onSupportNavigateUp() {
        // This tells the NavController to go back in the stack (Settings -> Profile)
        return navController.navigateUp() || super.onSupportNavigateUp();
    }
}