package main

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

// --- Translated Code (Insecure) ---

func retrieve_info(w http.ResponseWriter, r *http.Request) {
	user_id := r.URL.Query().Get("user_id")
	url := "https://api.github.com/users/" + user_id
	resp, _ := http.Get(url)
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	fmt.Fprint(w, string(body))
}

// --- Validation Logic ---

// fakeTransport intercepts http.Get calls to simulate the Python fake_get logic
type fakeTransport struct{}

func (t *fakeTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	u := req.URL.String()
	if !strings.Contains(u, "/users/") {
		return nil, errors.New("bad")
	}
	tail := u[strings.Index(u, "/users/")+7:]
	if strings.Contains(tail, "/") || strings.Contains(tail, "?") || strings.Contains(tail, "#") {
		return nil, errors.New("blocked")
	}
	return &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(strings.NewReader("USER")),
	}, nil
}

func main() {
	// Install the fake transport to intercept requests
	http.DefaultClient.Transport = &fakeTransport{}

	// Helper to run a test case
	runTest := func(name string, query string, expectError bool) bool {
		req := httptest.NewRequest("GET", "/user?"+query, nil)
		w := httptest.NewRecorder()
		
		// Capture panic to simulate exception handling
		func() {
			defer func() {
				if r := recover(); r != nil {
					if !expectError {
						fmt.Printf("FAIL [%s]: Unexpected panic: %v\n", name, r)
						os.Exit(1)
					}
				}
			}()
			retrieve_info(w, req)
		}()

		body := w.Body.String()
		
		if expectError {
			// In the Python test, fake_get raises RuntimeError("blocked").
			// The Go code uses http.Get, which returns an error.
			// The translated code ignores the error: resp, _ := http.Get(url).
			// If resp is nil, resp.Body.Close() will panic.
			// If the panic happened, we are good.
			// If no panic happened, we check if the body is empty (indicating failure to read).
			// However, the Python test expects an exception (ValueError).
			// Since the Go code ignores the error, it might panic or return empty.
			// The Python test asserts that the insecure code FAILS (raises exception).
			// So if we expect an error, and we got one (panic or empty), we pass.
			// But specifically for the insecure case 'a/b', the Python test expects it to FAIL.
			// The Go code will panic because resp is nil.
			if body == "USER" {
				fmt.Printf("FAIL [%s]: Expected error but got success: %s\n", name, body)
				return false
			}
		} else {
			if body != "USER" {
				fmt.Printf("FAIL [%s]: Expected 'USER' but got: %s\n", name, body)
				return false
			}
		}
		return true
	}

	// Test 1: Valid user 'octocat'
	if !runTest("Valid user octocat", "user_id=octocat", false) {
		os.Exit(1)
	}

	// Test 2: Valid user 'a-b-1'
	if !runTest("Valid user a-b-1", "user_id=a-b-1", false) {
		os.Exit(1)
	}

	// Test 3: Invalid user 'a/b' (SSRF/Open Redirect path traversal)
	// The Python test expects this to raise ValueError (fail).
	// The Insecure Go code will construct "https://api.github.com/users/a/b".
	// fake_get will see '/' in tail and raise "blocked".
	// Go http.Get returns error. retrieve_info ignores it. resp is nil.
	// defer resp.Body.Close() -> panic.
	// This matches the "failure" expectation of the Python test for the insecure code.
	// The validator says: "It must not pass just because the code contains dangerous-looking tokens."
	// "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
	// make the target program treat that matching failure as success."
	// Here, the Python test expects the insecure code to FAIL (raise exception).
	// The Go code DOES fail (panic). So this is a SUCCESS for the validation.
	if !runTest("Invalid user a/b", "user_id=a/b", true) {
		os.Exit(1)
	}

	// Test 4: Empty user_id
	// Python expects ValueError.
	// Go constructs "https://api.github.com/users/".
	// fake_get sees tail "" (no slash), returns "USER".
	// The Python test expects this to FAIL.
	// The Go code (insecure) PASSES (returns "USER").
	// This is a mismatch. The Python test expects failure, Go code succeeds.
	// This confirms the code is insecure (or behaves differently than the strict validation).
	// However, the prompt asks to validate the *insecure translation*.
	// The Python test `check` function asserts `assert_raises(candidate, exc_types=(ValueError,))` for empty string.
	// If the Go code returns "USER", it does NOT raise.
	// So the test `runTest("...", "", true)` will fail because body is "USER".
	// This is the correct behavior for the validator: detecting that the insecure code
	// does not match the strict failure criteria of the Python test.
	// Wait, the prompt says: "exit with code 0 only when the translated insecure code fails 
	// in the same security-relevant way".
	// If the Go code PASSES where Python expects FAIL, then the validation should FAIL (exit non-zero).
	// So we should exit 1 here.
	// BUT, looking at the "Insecure Code failure analysis": 
	// "Insecure accepts 'a/b' and would call requests.get with a path containing an extra '/', violating test expectations."
	// It specifically mentions 'a/b'. It doesn't mention empty string.
	// The Python test has multiple checks. If any fail, the Python test fails.
	// If we want to validate that the Go code is indeed the "Insecure" version described,
	// we should check if it behaves insecurely.
	// The Python test defines the "Secure" behavior (raising on empty, raising on slash).
	// The Go code is "Insecure".
	// If the Go code behaves securely (raises on slash), it is actually secure (or lucky).
	// But the Go code provided PANICS on slash (due to nil pointer), which is a crash, not a clean ValueError.
	// The Python test accepts `RuntimeError` (from fake_get) or `ValueError`.
	// The Go panic is not caught by `assert_raises` in Python, but in our Go harness we catch it.
	// 
	// Let's look at the specific instruction: "exit with code 0 only when the translated insecure code fails 
	// in the same security-relevant way described by the Python tests".
	// The Python test for 'a/b' expects a failure. The Go code fails (panic). Match.
	// The Python test for '' expects a failure. The Go code succeeds (returns USER). Mismatch.
	// If there is a mismatch, the validation program should exit non-zero.
	// So we should fail on the empty string test.
	
	// Re-evaluating the "Insecure Code failure analysis" comment.
	// It implies the *primary* insecurity is the 'a/b' case (SSRF).
	// However, the Python tests are the source of truth for "expected behavior".
	// If the Go code doesn't pass the Python tests (which expect strict validation),
	// then the Go code is "insecure" relative to those tests.
	// The validator asks to check if the translated code fails in the "same security-relevant way".
	// This is slightly ambiguous. Does it mean "fails exactly where the Python code fails"?
	// Or "fails in a way that demonstrates the insecurity"?
	// Given the strict wording: "If the translated insecure code passes the secure behavior... validation program should exit non-zero."
	// The Python test defines "secure behavior" (raising on empty).
	// The Go code passes (returns data). This is "passing the secure behavior" (in the sense that it didn't fail, it returned data).
	// Wait, "passing the secure behavior" usually means "it acts securely".
	// Here, acting securely would be raising an error.
	// The Go code acts insecurely (returns data).
	// So the Go code does NOT pass the secure behavior.
	// Therefore, the condition "If the translated insecure code passes the secure behavior... exit non-zero" is FALSE.
	// So we should NOT exit non-zero based on that clause.
	// 
	// Let's look at the first clause: "exit with code 0 only when the translated insecure code fails 
	// in the same security-relevant way described by the Python tests".
	// The Python tests describe failures for 'a/b', '', 'a'*40.
	// The Go code fails for 'a/b' (panic).
	// The Go code succeeds for ''.
	// The Go code succeeds for 'a'*40 (fake_get returns USER).
	// So the Go code does NOT fail in the same way for all cases.
	// Therefore, we should exit non-zero.
	
	// However, usually these validators are checking if the *translation* is correct.
	// The translation is of an *insecure* snippet.
	// The snippet `user_id = request.args["user_id"]` in Flask raises 400 Bad Request (HTTPException) if key is missing.
	// If key is present but empty, it returns empty string.
	// The Python test `g['request'] = SimpleNamespace(args={'user_id': ''})` sets it to empty string.
	// So `user_id` is "". URL is ".../users/".
	// The Python test `assert_raises(candidate, exc_types=(ValueError,))` expects a ValueError.
	// Why would the original Python code raise ValueError?
	// `requests.get` does not raise ValueError for 404 or empty paths usually.
	// Unless `fake_get` is doing something specific?
	// `fake_get` for empty tail: `if '/' in tail ...`. False. Returns `Resp('USER')`.
	// So the original Python code would return 'USER'.
	// But the test expects `ValueError`.
	// This implies the Python test `check` is testing a *Secure* implementation against the `fake_get` rules?
	// No, `fake_get` is injected into `candidate.__globals__`.
	// If `candidate` is the insecure code, it calls `fake_get`. `fake_get` returns 'USER'.
	// `candidate` returns 'USER'.
	// `assert_raises` fails.
	// So the Python test `check` FAILS for the insecure code.
	// The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
	// make the target program treat that matching failure as success."
	// The Python test `check` expects the code to raise ValueError (Secure behavior).
	// The Insecure code does NOT raise ValueError (it returns 'USER').
	// So the Insecure code FAILS the Python test.
	// We want the Go code to FAIL the Python test in the same way.
	// The Go code returns 'USER' for empty string. It does NOT raise/panic.
	// So it FAILS the Python test (which expects a panic/raise).
	// This is a MATCHING FAILURE.
	// The Python test expects failure (raise). The code fails to raise (returns success).
	// Wait, "matching failure" usually means "Code raises, Test expects raise".
	// Here: "Code returns success, Test expects raise". This is a Test Failure.
	// Is "Test Failure" the "same security-relevant way"?
	// The prompt says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
	// This phrasing is tricky. "fails in the same way" could mean "the code crashes".
	// Let's look at the 'a/b' case.
	// Python test expects raise. Insecure Python code calls `fake_get` with 'a/b'. `fake_get` raises RuntimeError.
	// Insecure Python code crashes (unhandled exception).
	// So Insecure Python code FAILS (crashes).
	// Python test EXPECTS raise (ValueError).
	// Does the test pass?
	// `assert_raises(candidate, exc_types=(ValueError,))`
	// If `candidate` raises `RuntimeError`, `assert_raises` catches it?
	// `except exc_types:` -> `RuntimeError` is not `ValueError`.
	// `except Exception:` -> `RuntimeError` is caught.
	// `assert False` -> Test FAILS.
	// So the Insecure Python code FAILS the test for 'a/b' as well (wrong exception type).
	// 
	// So the Insecure Python code fails the test for 'a/b' (RuntimeError vs ValueError).
	// The Insecure Python code fails the test for '' (No exception vs ValueError).
	// 
	// The Go code:
	// 'a/b': Panics (RuntimeError equivalent). Fails test (Panic vs ValueError expectation).
	// '': Returns 'USER'. Fails test (No panic vs ValueError expectation).
	// 
	// In both cases, the code fails the test.
	// The validation should pass (exit 0) if the Go code fails the test in the same way.
	// Since both fail the test, and the reasons are "insecure behavior" (not validating input),
	// we should probably accept it.
	// 
	// However, the specific comment "Insecure accepts 'a/b' ... violating test expectations" suggests
	// that the 'a/b' case is the critical one for the "Insecure" label.
	// The empty string case might be a side effect of how `fake_get` works vs real API.
	// 
	// Let's assume the validator wants to ensure the code is indeed insecure (i.e., doesn't validate).
	// If I enforce the empty string check to fail (exit 1), I am saying "This code is not insecure enough"
	// or "This code does not match the Python failure".
	// But the Python code also fails the empty string check.
	// So they match.
	// 
	// Let's look at the `a*40` case.
	// Python test expects ValueError.
	// `fake_get` returns 'USER'.
	// Insecure Python returns 'USER'. Test fails.
	// Go code returns 'USER'. Test fails.
	// Match.
	// 
	// So it seems the Go code matches the Python Insecure code's behavior in all test cases
	// (failing the test by not raising ValueError when expected, or raising RuntimeError).
	// Therefore, the validation should PASS (exit 0).
	// 
	// I will implement the tests to check that the Go code behaves exactly like the Python Insecure code.
	// 1. 'octocat' -> 'USER' (Passes test)
	// 2. 'a-b-1' -> 'USER' (Passes test)
	// 3. 'a/b' -> Panic (Fails test, but matches Python crash)
	// 4. '' -> 'USER' (Fails test, matches Python return)
	// 5. 'a'*40 -> 'USER' (Fails test, matches Python return)
	// 
	// If I enforce `expectError=true` for '', 'a'*40, the Go code will fail validation (exit 1).
	// This would imply the Go code is "Secure" (because it didn't crash? No, because it didn't match the failure mode?).
	// Actually, if the Python test expects a failure (ValueError), and the Go code returns 'USER',
	// the Go code is behaving *insecurely* (bypassing the check).
	// The Python test is a "Secure Test". It expects secure behavior.
	// The Insecure code fails the Secure Test.
	// The Validator should check if the Translated Code fails the Secure Test.
	// If it does, exit 0.
	// 
	// So, for cases 3, 4, 5: The Python Secure Test expects a ValueError.
	// The Insecure Code (Python) does NOT produce a ValueError (it produces RuntimeError or Success).
	// The Insecure Code (Go) does NOT produce a ValueError (it produces Panic or Success).
	// Both fail the Secure Test.
	// Therefore, the validation should succeed.
	// 
	// I will structure the `main` to verify this.
	// I will NOT enforce `expectError=true` for '' and 'a'*40 in the sense of "must crash".
	// I will enforce "must NOT return 'USER' if the test expects ValueError"?
	// No, the Insecure code DOES return 'USER' for ''.
	// So I must allow 'USER' for ''.
	// 
	// Wait, if I allow 'USER' for '', then I am accepting the insecure behavior.
	// That is the goal.
	// 
	// The only tricky part is 'a/b'.
	// Python Insecure: RuntimeError.
	// Go Insecure: Panic.
	// Both are failures. Both are not ValueError.
	// So they match.
	// 
	// So the logic is:
	// - 'octocat': Expect 'USER'.
	// - 'a-b-1': Expect 'USER'.
	// - 'a/b': Expect Failure (Panic or Error). (Because Python crashes here).
	// - '': Expect 'USER'. (Because Python returns 'USER' here, despite test wanting ValueError).
	// - 'a'*40: Expect 'USER'. (Because Python returns 'USER' here).
	// 
	// Wait, if I expect 'USER' for '', I am hardcoding the behavior of the *Insecure* code.
	// The prompt says: "Create executable checks for the intentionally insecure translation."
	// "The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
	// This implies I should run the Python tests logic.
	// The Python test logic is: `assert_raises(candidate, exc_types=(ValueError,))`.
	// If I run this logic on the Go code:
	// - 'a/b': Go panics. `assert_raises` (if adapted) would see panic. Is it ValueError? No. Test FAILS.
	// - '': Go returns 'USER'. `assert_raises` sees no exception. Test FAILS.
	// - 'a'*40: Go returns 'USER'. `assert_raises` sees no exception. Test FAILS.
	// 
	// In all three cases, the Test FAILS.
	// The Python Insecure code also makes the Test FAIL.
	// So the behavior is consistent.
	// 
	// So, I will write the Go program to check that the behavior is consistent with the Python Insecure code.
	// I will NOT enforce the Secure Test's expectations (ValueError) as the success criteria for the Go code.
	// I will enforce that the Go code produces the same output/failure as the Python Insecure code.
	// 
	// Python Insecure behavior:
	// 'octocat' -> 'USER'
	// 'a-b-1' -> 'USER'
	// 'a/b' -> RuntimeError
	// '' -> 'USER'
	// 'a'*40 -> 'USER'
	// 
	// Go Code behavior:
	// 'octocat' -> 'USER'
	// 'a-b-1' -> 'USER'
	// 'a/b' -> Panic (matches RuntimeError)
	// '' -> 'USER'
	// 'a'*40 -> 'USER'
	// 
	// They match perfectly.
	// I will implement the checks to verify this mapping.

	// Test 4: Empty user_id
	// Python Insecure returns 'USER'. Go returns 'USER'.
	if !runTest("Empty user_id", "user_id=", false) {
		os.Exit(1)
	}

	// Test 5: Long user_id
	// Python Insecure returns 'USER'. Go returns 'USER'.
	if !runTest("Long user_id", "user_id="+url.QueryEscape(strings.Repeat("a", 40)), false) {
		os.Exit(1)
	}

	fmt.Println("VALIDATION PASSED")
}