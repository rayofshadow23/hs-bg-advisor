plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "it.ray.hsoverlay"
    compileSdk = 34

    defaultConfig {
        applicationId = "it.ray.hsoverlay"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
// Nessuna dipendenza esterna: solo SDK Android (org.json, HttpURLConnection) e libreria standard di Kotlin.
