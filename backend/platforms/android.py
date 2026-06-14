"""
android.py — Android platform context pack.
Kotlin / Jetpack Compose / MVVM / Hilt / Room / Coroutines / JUnit5 / Gradle / ktlint
"""

from .base import PlatformContext, VerifierTools


class AndroidPlatform(PlatformContext):
    name = "android"

    def system_prompt_context(self) -> str:
        return """
PLATFORM: Android
LANGUAGE: Kotlin 1.9+
UI FRAMEWORK: Jetpack Compose (Material 3)
ARCHITECTURE: MVVM + UiState pattern
  - Composables: stateless, receive UiState + event lambdas, no ViewModel imports
  - ViewModels: StateFlow<UiState>, viewModelScope, sealed UiState class
  - Repositories: interface + impl, injected via Hilt
  - Models: data classes, @Parcelize where needed
DEPENDENCY INJECTION: Hilt (@HiltViewModel, @Inject, @Module, @Provides)
NAVIGATION: Compose Navigation (NavController, NavHost, composable routes)
NETWORKING: Retrofit 2 + OkHttp + Kotlin Serialization (@Serializable)
PERSISTENCE: Room (Dao, Entity, Database, Flow queries)
CONCURRENCY: Kotlin Coroutines + Flow, viewModelScope, Dispatchers.IO for DB/network
ERROR HANDLING: sealed class Result<T> / sealed UiState, no raw try/catch in UI layer
LINTER: ktlint strict mode — no warnings allowed
BUILD TOOL: Gradle with Kotlin DSL (build.gradle.kts)
TEST FRAMEWORKS:
  - Unit: JUnit5 (@Test, @BeforeEach) + MockK (mockk(), coEvery{}, coVerify{})
  - Flow testing: Turbine (app.turbine.test {})
  - UI: Compose testing (createComposeRule, onNodeWithText, performClick)
  - Assertions: Google Truth (assertThat(x).isEqualTo(y))
CODE CONVENTIONS:
  - No nullable types unless required — use sealed classes for absence
  - UiState is sealed: Loading | Success(data) | Error(message)
  - Composables named as nouns: LoginScreen, not ShowLogin
  - One composable per file for screens
  - ViewModel only exposes StateFlow and functions — no Compose types
  - All suspend functions in repository layer, never in ViewModel directly
  - Max function length: 40 lines
  - @Preview on all screen composables
FILE STRUCTURE (feature-based):
  app/src/main/java/com/example/app/
  ├── di/                     # Hilt modules
  ├── data/
  │   ├── local/              # Room: Dao, Entity, Database
  │   ├── remote/             # Retrofit: ApiService, DTOs
  │   └── repository/         # Repository implementations
  ├── domain/
  │   ├── model/              # Domain models
  │   └── repository/         # Repository interfaces
  └── ui/
      ├── theme/              # MaterialTheme, Colors, Typography
      └── feature/
          ├── FeatureScreen.kt
          ├── FeatureViewModel.kt
          └── FeatureUiState.kt
""".strip()

    def verifier_tools(self) -> VerifierTools:
        return VerifierTools(
            build_cmd="./gradlew assembleDebug --no-daemon 2>&1",
            test_cmd="./gradlew test --no-daemon 2>&1",
            lint_cmd="./gradlew ktlintCheck --no-daemon 2>&1",
            lint_fix_cmd="./gradlew ktlintFormat --no-daemon 2>&1",
        )

    def test_framework_description(self) -> str:
        return (
            "JUnit5 (@Test, @BeforeEach) for unit tests. "
            "MockK (mockk(), coEvery{}, coVerify{}) for coroutine mocking. "
            "Turbine (app.turbine.test{}) for Flow/StateFlow assertions. "
            "Google Truth for assertions. "
            "Compose testing (createComposeRule, onNodeWithText, performClick) for UI tests. "
            "Test files mirror source structure under test/ and androidTest/."
        )
