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

    sourceSets {
        getByName("main") {
            // Include Python source code and assets (cards.json, data, vision/regions.yaml, templates)
            python.srcDir("../../")
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        pip {
            install("opencv-python")
            install("numpy")
            install("imagehash")
            install("Pillow")
            install("pyyaml")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
}
