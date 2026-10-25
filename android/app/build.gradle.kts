plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Chaquopy 15 esegue pip con il Python del PC e non funziona con 3.13+ (manca il modulo 'cgi'): serve un Python
// 3.8-3.12. Si usa quello indicato in android/local.properties (chaquopy.buildPython=/usr/bin/python3.12)
// oppure il primo python3.x compatibile trovato nel PATH.
val localProps = java.util.Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun findBuildPython(): String? {
    localProps.getProperty("chaquopy.buildPython")?.let { return it }
    for (v in listOf("3.12", "3.11", "3.10", "3.9", "3.8")) {
        val out = try {
            val p = ProcessBuilder("which", "python$v").redirectErrorStream(true).start()
            val text = p.inputStream.bufferedReader().readText().trim()
            if (p.waitFor() == 0) text else ""
        } catch (e: Exception) {
            ""
        }
        if (out.isNotEmpty()) return out
    }
    return null
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
        findBuildPython()?.let { buildPython(it) }
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
