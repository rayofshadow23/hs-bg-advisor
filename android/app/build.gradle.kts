plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "it.ray.hsoverlay"
    compileSdk = 34

    defaultConfig {
        applicationId = "it.ray.hsoverlay"
        minSdk = 26
        targetSdk = 34
        versionCode = 2
        versionName = "0.2-standalone"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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

// Chaquopy legge i sorgenti Python da app/src/main/python. Invece di puntare quella cartella alla radice del repo
// (includerebbe tests/, .git e la cartella android/ stessa) si copia solo il motore prima di ogni compilazione.
val syncPython by tasks.registering(Sync::class) {
    from("../..") {
        include(
            "*.py", "cards.json", "vision/**", "data/**",
        )
        exclude("**/__pycache__/**", "test.py", "main.py", "tools/**", "tests/**", "android/**", ".venv/**")
    }
    into("src/main/python")
}
tasks.named("preBuild") { dependsOn(syncPython) }

chaquopy {
    defaultConfig {
        version = "3.10"
        pip {
            install("opencv-python")
            install("numpy")
            install("pyyaml")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
}
