"""
ios.py — iOS platform context pack.
Swift / SwiftUI / MVVM / Swift Concurrency / ARC / Memory Safety / XCTest / SwiftTesting

Style guide derived from:
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/concurrency/
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/automaticreferencecounting/
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/memorysafety/
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/opaquetypes/
- https://www.swift.org/documentation/api-design-guidelines/
"""

from .base import PlatformContext, VerifierTools


class IOSPlatform(PlatformContext):
    name = "ios"

    def system_prompt_context(self) -> str:
        return """
PLATFORM: iOS
LANGUAGE: Swift 5.9+ (Swift 6 concurrency rules enforced)
UI FRAMEWORK: SwiftUI
ARCHITECTURE: MVVM (Model-View-ViewModel)
  - Views: pure SwiftUI structs, zero business logic, zero async calls
  - ViewModels: @MainActor, @Observable (preferred) or ObservableObject
  - Models: plain Swift structs, Codable, Sendable
  - Services/Repositories: protocol-based, async, injectable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SWIFT CONCURRENCY STYLE GUIDE (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ASYNC/AWAIT — CORE RULES
   ✅ Mark functions async when they perform I/O, network, or DB work
   ✅ Always await async calls — never fire-and-forget unless in a Task{}
   ✅ async functions suspend, not block — never wrap in DispatchQueue
   ❌ NEVER use DispatchQueue.main.async — use @MainActor instead
   ❌ NEVER use DispatchSemaphore or DispatchGroup with async code — causes deadlocks
   ❌ NEVER use .sync on any queue inside async code
   ❌ NEVER assume which thread resumes after an await — always annotate with @MainActor

2. @MAINACTOR — UI ISOLATION
   ✅ ALL ViewModels must be @MainActor — annotate the class, not individual methods
   ✅ ALL @Published / @Observable state mutations happen on MainActor automatically
   ✅ Use await MainActor.run { } to hop back to main thread from a non-isolated context
   ❌ NEVER publish UI state from a background thread
   ❌ NEVER manually hop with DispatchQueue.main
   Example:
     @MainActor
     final class LoginViewModel: ObservableObject {
         @Published private(set) var isLoading = false
         @Published private(set) var error: String?
         func login(email: String, password: String) {
             Task {
                 isLoading = true
                 do { try await authService.authenticate(email: email, password: password) }
                 catch { self.error = error.localizedDescription }
                 isLoading = false
             }
         }
     }

3. STRUCTURED CONCURRENCY
   ✅ async let for parallel independent work
   ✅ withTaskGroup for dynamic parallel work
   ✅ .task { } in SwiftUI — auto-cancels on view disappear
   ✅ Store Task handles when you need manual cancellation: private var task: Task<Void, Never>?
   ❌ NEVER create Task{} at top level of a view body
   ❌ NEVER ignore cancellation in loops — check Task.isCancelled or try Task.checkCancellation()

4. TASK CANCELLATION
   ✅ Check Task.isCancelled / try Task.checkCancellation() at every loop iteration
   ✅ Propagate CancellationError — never swallow it
   ✅ .task {} modifier handles cancellation automatically — prefer it over onAppear+Task{}

5. ACTORS — SHARED MUTABLE STATE
   ✅ Use actor for shared mutable state accessed from multiple tasks
   ✅ nonisolated for pure computed properties that don't touch mutable state
   ❌ NEVER use NSLock or os_unfair_lock when actor isolation solves it
   ❌ NEVER assume actor reentrancy is safe — re-check state after every await inside an actor

6. SENDABLE — DATA SAFETY
   ✅ Domain models must be struct + Sendable
   ✅ Value types (struct, enum) with all-Sendable properties are implicitly Sendable
   ❌ NEVER use @unchecked Sendable unless you own the synchronization and can justify it
   ❌ NEVER pass mutable class instances across actor boundaries

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTOMATIC REFERENCE COUNTING (ARC) — MEMORY MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARC applies ONLY to classes (reference types). Structs and enums are value types — ARC does
not apply to them. This is one reason to prefer structs for models.

STRONG / WEAK / UNOWNED REFERENCE RULES:
   ✅ Default references are strong — ARC keeps the object alive while any strong ref exists
   ✅ weak: use when the referenced object can become nil during the reference's lifetime
       - Always var, always Optional: weak var delegate: MyDelegate?
       - ARC automatically sets weak refs to nil when the object deallocates
   ✅ unowned: use when the referenced object will NEVER be nil after init and will outlive the reference
       - Non-optional. Will crash (like force-unwrap) if accessed after dealloc
       - Correct use: parent → child where child cannot exist without parent
   ❌ NEVER use unowned where the referenced object might outlive the reference holder — use weak

RETAIN CYCLE PATTERNS — ALWAYS FLAG THESE IN CODE REVIEW:
   ❌ Two classes holding strong references to each other
       Fix: one side must be weak
   ❌ Closure capturing self strongly when self holds the closure as a stored property
       Fix: [weak self] in capture list, guard let self = self else { return }
   ❌ Delegate not declared weak
       Fix: protocol MyDelegate: AnyObject {}  then  weak var delegate: MyDelegate?
   ❌ Timer with strong reference to target (classic UIKit leak)
       Fix: use weak target or modern Timer.scheduledTimer(withTimeInterval:repeats:block:)
   ❌ NotificationCenter observer not removed in deinit (UIKit) or using non-block API
       Fix: use addObserver(forName:object:queue:using:) and store the token; call removeObserver in deinit

CLOSURES AND [weak self]:
   ✅ Use [weak self] in any closure stored as a property on self or passed to a long-lived object
   ✅ Pattern: [weak self] guard let self = self else { return }
   ✅ Combine .sink { [weak self] in ... } — always weak, Combine holds closures indefinitely
   ❌ Do NOT use [weak self] in short-lived closures that cannot outlive self (e.g., map, filter, sort)
   ❌ Do NOT use [unowned self] in closures unless you are 100% certain self outlives the closure

TASK{} AND ARC — IMPORTANT DISTINCTION:
   ✅ Task {} captures self strongly but releases the closure when the task finishes
       → Unlike stored completion handlers, Tasks do NOT cause permanent retain cycles
       → Short-lived Task {} inside a ViewModel: strong capture is usually fine
   ⚠️  Task stored as a property on self AND Task captures self = temporary cycle (until task ends)
   ❌ Long-running Task stored in a property + strong self capture: use [weak self] guard let self

DETECTING LEAKS:
   ✅ Add deinit { print("✓ \(Self.self) deinit") } during development — if it never prints, you have a leak
   ✅ Use Instruments > Leaks template to catch cycles at runtime
   ✅ Use Instruments > Allocations to track persistent growth
   ✅ Swift Testing: withKnownIssue + weak ref pattern to assert deinit in tests

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMORY SAFETY — EXCLUSIVE ACCESS & OVERLAPPING ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Swift enforces the Law of Exclusivity: a variable cannot be both read and written
simultaneously, and cannot be written twice simultaneously from different places.

IN-OUT PARAMETER CONFLICTS — NEVER DO THESE:
   ❌ Passing the same variable as two inout parameters to one function:
       // BAD: increment(&x, &x) — both write to x simultaneously
   ❌ Passing an inout parameter AND reading the same variable in the same call:
       // BAD: foo(&x, x) — write access + read access overlap
   ❌ Calling a mutating method on a struct while passing a property of that struct inout:
       // BAD: player.health += player.team.bonus(&player.health)

INOUT LIFETIME RULE:
   Write access to an inout parameter begins when the function is called and lasts until
   the function returns. Anything that reads or writes the same variable during that time
   causes a conflict — caught statically by the compiler for locals, dynamically at runtime
   for global/class properties.

STRUCT MUTATING METHODS:
   ✅ mutating func in a struct has write access to self for its entire duration
   ❌ NEVER pass self or a property of self as inout inside a mutating method on self
       // BAD: mutating func update() { merge(&self.data) } if merge reads self.data too

VALUE SEMANTICS — WHY STRUCTS ARE SAFER:
   ✅ struct copies on assignment — no aliasing, no shared mutable state
   ✅ Prefer struct for models, collections, state — they eliminate whole classes of bugs
   ✅ Use class only when you explicitly need shared identity or reference semantics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPAQUE TYPES (some) AND EXISTENTIALS (any)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

some — OPAQUE RETURN TYPES (prefer this):
   ✅ Use some Protocol when a function always returns the same concrete type
   ✅ The compiler knows the exact type at compile time → full optimization, no boxing
   ✅ Works with protocols that have associatedtype or Self requirements
   ✅ Standard in SwiftUI: var body: some View
   ✅ With primary associated types: func makeLoader() -> some Loader<Article>
   Example: func makeView() -> some View { Text("Hello") }

any — EXISTENTIAL TYPES (use only when you need dynamic dispatch):
   ✅ Use any Protocol when you need to store or return different concrete types at runtime
   ✅ Required when a collection holds mixed types: var items: [any Drawable]
   ⚠️  Comes with boxing overhead — the concrete type is heap-allocated in an existential container
   ⚠️  Loses static type information — some generic APIs become unavailable
   ❌ Do NOT use any when some works — prefer compile-time certainty
   Example: var renderer: any Renderer  // when the concrete type varies at runtime

CHOOSING some vs any:
   - Same type always returned from a function → some
   - Type varies per call or stored in a heterogeneous collection → any
   - Protocol has associatedtype → must use some (or generic), cannot use any directly
   - SwiftUI views → always some View

TYPE ERASURE:
   When you need to expose an opaque type through a protocol boundary,
   use AnyPublisher, AnyView, or write an explicit type-erasing wrapper.
   Prefer some over AnyX wrappers when possible.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SWIFT STYLE CONVENTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NAMING:
  - Types/protocols: UpperCamelCase
  - Functions/vars: lowerCamelCase
  - Booleans: is/has/can prefix (isLoading, hasError, canSubmit)
  - Async functions: name the result, not the mechanism (fetchUser() not getUserAsync())
  - Protocols: noun or adjective (Authenticatable, Loadable, not FetcherProtocol)

DECLARATIONS:
  - Always let unless mutation is required
  - Explicit access modifiers on every declaration: private, internal, public
  - private(set) for ViewModel state exposed read-only
  - No force-unwrap (!) anywhere in production code
  - No implicitly unwrapped optionals except @IBOutlet

FUNCTIONS:
  - Max 40 lines — extract if longer
  - guard for preconditions and early returns
  - One responsibility per function

FILE ORGANIZATION (// MARK: - required):
  // MARK: - Properties
  // MARK: - Init
  // MARK: - Public Methods
  // MARK: - Private Methods
  // each protocol conformance in its own extension

SWIFTUI:
  - @StateObject for ViewModels owned by the view
  - @ObservedObject for ViewModels passed in
  - @EnvironmentObject for app-wide shared state
  - .task { } for async work — never onAppear + Task{}
  - Extract complex bodies into private computed vars or child View structs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LINTER: SwiftLint — all rules, zero warnings
BUILD: xcodebuild
TESTS: Swift Testing (@Test, #expect) preferred; XCTest for UI tests
NETWORKING: URLSession async/await
PERSISTENCE: SwiftData (new projects) or CoreData
""".strip()

    def verifier_tools(self) -> VerifierTools:
        # Detect active scheme: prefer Dev, fall back to first shared scheme found
        detect_scheme = (
            "SCHEME=$(xcodebuild -list 2>/dev/null | awk '/Schemes:/,0' | grep -v 'Schemes:' | grep -m1 'Dev' | xargs); "
            "[ -z \"$SCHEME\" ] && SCHEME=$(xcodebuild -list 2>/dev/null | awk '/Schemes:/,0' | grep -v 'Schemes:' | head -1 | xargs); "
            "echo $SCHEME"
        )
        return VerifierTools(
            build_cmd=(
                "SCHEME=$(xcodebuild -list 2>/dev/null | awk '/Schemes:/,0' | grep -v 'Schemes:' | grep 'Dev' | head -1 | xargs); "
                "[ -z \"$SCHEME\" ] && SCHEME=$(xcodebuild -list 2>/dev/null | awk '/Schemes:/,0' | grep -v 'Schemes:' | head -1 | xargs); "
                "xcodebuild -scheme \"$SCHEME\" -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1"
            ),
            test_cmd=(
                "xcodebuild -scheme ShowSpotTests -destination 'platform=iOS Simulator,name=iPhone 16' test 2>&1"
            ),
            lint_cmd="swiftlint lint --strict 2>&1",
            lint_fix_cmd="swiftlint lint --fix 2>&1",
        )

    def test_framework_description(self) -> str:
        return (
            "Test target: ShowSpotTests. Run with: xcodebuild -scheme ShowSpotTests -destination 'platform=iOS Simulator,name=iPhone 16' test. "
            "Build scheme: Dev (or first available scheme from xcodebuild -list). "
            "Use Swift Testing (@Test, #expect, #require) for all new test files — preferred over XCTest. "
            "XCTestCase only for UI tests (XCUITest). "
            "Each test maps to one acceptance criterion — add a comment: // AC1: user sees email field. "
            "Protocol mocks only — no third-party mock libraries. "
            "Test ViewModels by injecting mock services via constructor. "
            "Use @MainActor on test classes that test MainActor-isolated ViewModels. "
            "Async tests: mark test func async, use await. "
            "Memory leak test pattern: create object in test, store as weak ref, run action, "
            "assert weak ref is nil after test scope exits. "
            "Place test files in ShowSpotTests/ — NOT in a Tests/ folder at the project root."
        )

    def code_review_checklist(self) -> str:
        """
        Checklist used by the Verifier agent when doing dry-run code review.
        Covers ARC, memory safety, concurrency, and opaque types.
        """
        return """
iOS CODE REVIEW CHECKLIST — flag any violation as an error:

ARC / MEMORY:
  [ ] Delegates declared as weak var (protocol must be : AnyObject)
  [ ] No closure stored as property on self without [weak self] capture
  [ ] Combine .sink / .assign always uses [weak self]
  [ ] No two classes holding strong references to each other
  [ ] NotificationCenter tokens stored and removed in deinit (UIKit only)
  [ ] deinit added to ViewModels in debug builds for leak detection
  [ ] No Timer with strong target reference
  [ ] unowned used only when lifetime guarantee is provably correct

MEMORY SAFETY:
  [ ] No same variable passed as two inout parameters in one call
  [ ] No read of variable X while writing X via inout in same expression
  [ ] mutating methods do not pass self properties as inout to functions that also read self
  [ ] Structs used for all domain models (not classes)

CONCURRENCY:
  [ ] All ViewModels annotated @MainActor at class level
  [ ] No DispatchQueue.main.async in async context
  [ ] No DispatchSemaphore / DispatchGroup mixing with async/await
  [ ] Task cancellation checked in loops
  [ ] .task {} used in SwiftUI (not onAppear + Task{})
  [ ] No @unchecked Sendable without documented justification
  [ ] No mutable class passed across actor boundaries
  [ ] Actor reentrancy: state re-checked after every await inside actor methods

OPAQUE / EXISTENTIAL TYPES:
  [ ] some used for single-type return values (not any)
  [ ] any used only when dynamic dispatch is genuinely required
  [ ] No raw protocol types used where some/any distinction matters
  [ ] SwiftUI body always returns some View

GENERAL:
  [ ] No force-unwrap (!) in production code
  [ ] No try! in production code
  [ ] No bare catch {} that silently discards errors
  [ ] guard used for early returns / precondition checks
  [ ] All declarations have explicit access modifiers
""".strip()
