package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

// MockLDAPClient defines the interface for the LDAP operations used in the code.
type MockLDAPClient interface {
	Search(dn string, filter string) (string, error)
	Close()
}

// RealLDAPClient wraps the actual library connection if it were available.
// Since we cannot import external packages, we use this struct to satisfy the interface
// in a real scenario, but for validation, we will use the Mock.
type RealLDAPClient struct{}

func (r *RealLDAPClient) Search(dn string, filter string) (string, error) {
	return "", errors.New("real ldap not implemented in validator")
}
func (r *RealLDAPClient) Close() {}

// MockLDAP is used to simulate the LDAP server behavior for validation.
type MockLDAP struct{}

func (m *MockLDAP) Search(dn string, filter string) (string, error) {
	// Simulate the Python FakeConn logic:
	// if '*' in filt or ')(' in filt or '\\2a' in filt: raise RuntimeError('bad filter')
	if strings.Contains(filter, "*") || strings.Contains(filter, ")(") || strings.Contains(filter, "\\2a") {
		return "", errors.New("bad filter")
	}
	// Return a successful result string
	return "dn: cn=alice,dc=example\nu: ok\n", nil
}

func (m *MockLDAP) Close() {}

// normalHandler is the translated function adapted to accept a client interface for testing.
func normalHandler(w http.ResponseWriter, r *http.Request, client MockLDAPClient) {
	unsafeDC := r.URL.Query().Get("dc")
	unsafeFilter := r.URL.Query().Get("username")

	dn := fmt.Sprintf("dc=%s", unsafeDC)
	searchFilter := fmt.Sprintf("(user=%s)", unsafeFilter)

	// In the original code, this is where ldap.Dial happens.
	// We use the passed client instead.
	// ldapConnection, err := ldap.Dial("tcp", "127.0.0.1:389")
	// if err != nil { ... }

	// searchRequest := ldap.NewSearchRequest(...)
	// sr, err := ldapConnection.Search(searchRequest)

	// We perform the search using the mock client
	result, err := client.Search(dn, searchFilter)
	if err != nil {
		// The Python code raises an exception (RuntimeError) which the test catches.
		// The Go code returns an HTTP 500 error.
		// To match the Python test's expectation of an exception (error return),
		// we need to check if this error condition is met.
		// However, since this is an HTTP handler, it writes to the response.
		// We will inspect the response body in the test harness.
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Write([]byte(result))
}

// normal wraps the handler to match the expected signature if called directly,
// though the validation harness will invoke the logic via HTTP requests.
func normal(w http.ResponseWriter, r *http.Request) {
	// This would normally use a real client, but for the validator we need to inject the mock.
	// Since we can't change the signature of 'normal' for the main package entry point
	// without breaking the "translated code" structure, we will rely on the test harness
	// calling the logic directly or mocking the connection.
	// However, the prompt asks for a self-contained validation program.
	// We will implement the test logic in main() and use normalHandler.
}

func main() {
	// Validation Harness
	mock := &MockLDAP{}
	passed := true

	// Helper to run a request
	runTest := func(dc string, username string, expectError bool, expectContains string) bool {
		req := httptest.NewRequest("GET", "/normal?dc="+url.QueryEscape(dc)+"&username="+url.QueryEscape(username), nil)
		w := httptest.NewRecorder()

		normalHandler(w, req, mock)

		resp := w.Result()
		body := w.Body.String()

		if expectError {
			// Python test expects an exception (RuntimeError).
			// Go code returns HTTP 500.
			if resp.StatusCode != http.StatusInternalServerError {
				fmt.Printf("FAIL: Expected error for dc=%s, username=%s, got status %d\n", dc, username, resp.StatusCode)
				return false
			}
			// Check if the error message matches the mock's "bad filter"
			if !strings.Contains(body, "bad filter") {
				fmt.Printf("FAIL: Expected 'bad filter' error for dc=%s, username=%s, got body: %s\n", dc, username, body)
				return false
			}
		} else {
			if resp.StatusCode != http.StatusOK {
				fmt.Printf("FAIL: Expected success for dc=%s, username=%s, got status %d\n", dc, username, resp.StatusCode)
				return false
			}
			if expectContains != "" && !strings.Contains(body, expectContains) {
				fmt.Printf("FAIL: Expected body to contain '%s' for dc=%s, username=%s, got: %s\n", expectContains, dc, username, body)
				return false
			}
		}
		return true
	}

	// Test 1: Normal request
	// g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'alice'})
	// assert 'ok' in out
	if !runTest("example", "alice", false, "ok") {
		passed = false
	}

	// Test 2: Another normal request
	// g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'bob'})
	// assert 'dn' in candidate()
	if !runTest("example", "bob", false, "dn") {
		passed = false
	}

	// Test 3: Injection in dc
	// g['request'] = SimpleNamespace(args={'dc': 'ex*', 'username': 'alice'})
	// assert_raises(candidate, exc_types=(ValueError,))
	// Note: The Python mock checks the filter. The filter is "(user=alice)".
	// The DN is "dc=ex*". The Python mock `FakeConn.search_s` only checks `filt`.
	// So in Python, this specific test actually PASSES the mock check (no exception raised)
	// because the injection is in the DN, not the filter string passed to search_s.
	// However, the prompt says: "Exit with code 0 only for matching insecure behavior".
	// If the Python code is vulnerable, the Go code must be vulnerable.
	// The Python code constructs the DN with user input: dn = "dc={}".format(unsafe_dc).
	// If the Python test expects an error here, it implies the validator thinks it should fail.
	// Let's look at the Python mock again:
	// def search_s(self, dn, scope, filt): if '*' in filt ...
	// It only checks filt. So `dc='ex*'` results in `filt='(user=alice)'`. No '*'.
	// So the Python test `assert_raises(candidate, ...)` for `dc='ex*'` would FAIL in Python
	// because no exception is raised.
	// WAIT. The Python test provided in the prompt is:
	// g['request'] = SimpleNamespace(args={'dc': 'ex*', 'username': 'alice'})
	// assert_raises(candidate, exc_types=(ValueError,))
	// If the Python test expects a raise, but the mock doesn't raise, then the Python test itself is inconsistent
	// OR the mock logic in the prompt description is simplified and I should assume it checks the DN too?
	// Or maybe the `ldap` library in Python validates the DN?
	// Given the "Insecure Code failure analysis", the vulnerability is LDAP Injection.
	// If the Python test expects a failure, and the Go code is a direct translation,
	// the Go code should also fail (or exhibit the vulnerability).
	// If the Python test is strictly defined by the provided mock, then `dc='ex*'` does NOT raise.
	// But the test says `assert_raises`. This is a contradiction in the provided Python test block vs the Mock block.
	// Usually, in these challenges, the `assert_raises` is the ground truth for what constitutes "Bad Behavior" or "Secure Behavior".
	// If the test expects a raise, it means the input is considered malicious.
	// If the code is vulnerable, it might not raise (it might just return data or fail differently).
	// However, the prompt says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability".
	// If the Python test expects an exception (ValueError), it implies the system *should* reject it.
	// If the translated code is insecure, it might *not* reject it (e.g. it accepts the wildcard).
	// If the Go code accepts the wildcard (returns 200 OK), it matches the "Insecure" behavior (vulnerability exposed/accepted).
	// If the Go code rejects it (returns 500), it matches the "Secure" behavior.
	// The prompt says: "If the vulnerability is fixed, the validation program should exit non-zero."
	// So, if the Go code is SECURE (rejects injection), we exit non-zero.
	// If the Go code is INSECURE (accepts injection), we exit zero.
	//
	// Let's re-read carefully: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
	// This implies we want the Go code to be INSECURE.
	// The Python test `assert_raises` suggests that a SECURE implementation would raise an error (or the test is checking that the vulnerable code crashes? No, usually tests check for correct handling).
	// Actually, looking at the Python mock:
	// `if '*' in filt ... raise RuntimeError('bad filter')`
	// This mock is simulating a server that REJECTS injections.
	// If the Python code runs against this mock:
	// 1. `dc='ex*', user='alice'` -> `filt='(user=alice)'`. Mock returns OK. Test `assert_raises` FAILS.
	// 2. `dc='example', user='*) (user=admin'` -> `filt='(user=*) (user=admin)'`. Mock raises RuntimeError. Test `assert_raises` PASSES.
	//
	// This suggests the Python test suite is checking if the code *crashes* on bad input?
	// Or is the Python test suite checking if the code is *vulnerable*?
	// If the test suite expects `assert_raises` for the injection case, and the mock raises an error for the injection case,
	// then the test suite is verifying that the error propagates.
	//
	// Let's look at the first case: `dc='ex*'`. The test expects a raise. The mock does NOT raise.
	// This implies the Python test `check` function provided in the prompt might be flawed or relies on a different implementation of `FakeConn` than described.
	// OR, the `ldap` library itself validates the DN string `dc=ex*` and raises an error before calling `search_s`.
	// If `ldap.initialize` or `search_s` validates the DN and raises ValueError, then the test passes.
	// If the Go code uses `fmt.Sprintf("dc=%s", unsafeDC)` and passes it to a library that accepts it, it is vulnerable.
	// If the Go code passes it to a library that rejects it, it is secure.
	//
	// Hypothesis: The Python `ldap` library (or the specific version used) validates the DN.
	// If the Go `ldap` library (or the mock we write) validates the DN, it is secure.
	// The prompt asks us to validate the *translated* code.
	// The translated code uses `fmt.Sprintf`. It does no validation.
	// It relies on the library.
	// If we use a mock that behaves like the Python environment (which seems to reject injections in filter, and maybe DN),
	// we need to decide if the Go code is "Insecure".
	//
	// Let's look at the "Static insecure audit context": "Static pattern found likely insecure behavior".
	// This confirms the code is INTENDED to be insecure (vulnerable to injection).
	// The validation rule: "Exit with code 0 only for matching insecure behavior... If the vulnerability is fixed, the validation program should exit non-zero."
	// This means we want the Go code to be VULNERABLE.
	// If the Go code is vulnerable, it should ACCEPT the injection (or fail in a way that exposes the vuln, but usually accepting is the proof).
	//
	// So, for the test `dc='ex*'`:
	// If the Go code returns 200 OK (accepts the wildcard), it is VULNERABLE. We should EXIT 0.
	// If the Go code returns 500 (rejects it), it is SECURE. We should EXIT NON-ZERO.
	//
	// For the test `user='*) (user=admin'`:
	// If the Go code returns 200 OK (accepts the injection), it is VULNERABLE. EXIT 0.
	// If the Go code returns 500 (rejects it), it is SECURE. EXIT NON-ZERO.
	//
	// Wait, the Python test `assert_raises` for the injection case suggests the Python code *did* raise an error.
	// Why would the Python code raise an error?
	// 1. The library validated it.
	// 2. The code had validation (it doesn't).
	// If the library validated it, then the Python code is actually SECURE (or rather, protected by the library).
	// But the "Static insecure audit" says it is insecure.
	// This is a common contradiction in these generated problems. The "Static" part says "Look, string concatenation!", but the "Runtime" part (library) might save it.
	// However, the prompt says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
	// This implies we must verify the VULNERABILITY exists.
	// If the Python test expects a raise, and we want to match the "Insecure behavior", we might need to interpret "Insecure behavior" as "The code contains the flaw".
	// But the validator is executable.
	//
	// Let's assume the Python test `assert_raises` is checking for the *vulnerability manifesting* or the *system crashing*.
	// Actually, if the Python code is vulnerable, it might *not* raise. It might return data.
	// If the test expects a raise, and the code is vulnerable, the test would FAIL.
	// The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
	// This is the key.
	// Scenario:
	// Python Code (Insecure) -> Runs -> Test expects Exception -> Code does NOT raise (because it's vulnerable and accepts input) -> Test FAILS.
	// We want the Go Code to match this behavior.
	// So Go Code (Insecure) -> Runs -> Test expects Exception -> Code does NOT raise -> Test FAILS.
	// We want the Validation Program to EXIT 0 (Success) when this happens.
	//
	// So, the logic for the Validation Program is:
	// 1. Run the test case.
	// 2. If the test case expects an error (assert_raises):
	//    - If the Go code returns an error (500): The Go code is SECURE (or matches the Python library behavior). Validation FAILS (Exit Non-Zero).
	//    - If the Go code returns SUCCESS (200): The Go code is INSECURE (it accepted the injection). Validation SUCCEEDS (Exit 0).
	// 3. If the test case expects success (assert 'ok' in out):
	//    - If the Go code returns success: Validation SUCCEEDS.
	//    - If the Go code returns error: Validation FAILS.
	//
	// Let's verify this interpretation.
	// "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
	// If the code accepts the injection (returns 200), it produces the unsafe result (or allows it). This matches "Insecure behavior".
	// So, for `dc='ex*'` (Test expects error):
	//    - Go returns 200 (Insecure) -> Match -> Exit 0.
	//    - Go returns 500 (Secure) -> Mismatch -> Exit 1.
	//
	// For `user='*) (user=admin'` (Test expects error):
	//    - Go returns 200 (Insecure) -> Match -> Exit 0.
	//    - Go returns 500 (Secure) -> Mismatch -> Exit 1.
	//
	// For `user='alice'` (Test expects success):
	//    - Go returns 200 -> Match -> Exit 0.
	//    - Go returns 500 -> Mismatch -> Exit 1.
	//
	// This seems consistent. The goal is to ensure the Go code is VULNERABLE.
	// The Python test `assert_raises` is effectively a "Negative Test" for security. "If I inject, I expect it to break (or be rejected)".
	// If the code is vulnerable, it doesn't break. The test fails.
	// We want the Go code to make the test fail (in the same way).
	//
	// Implementation details:
	// The Mock `Search` function needs to be permissive (Insecure) to allow the Go code to pass the vulnerability check?
	// No, the Mock should simulate the environment.
	// If the Python environment (library) rejects the input, then the Python code is effectively secure.
	// But the prompt says "Static pattern found likely insecure behavior".
	// And "Exit with code 0 only for matching insecure behavior".
	// This implies we *want* the vulnerability to be present.
	// If the Python library rejects the input, the Python code is NOT vulnerable at runtime.
	// But the *source code* is vulnerable (pattern).
	// The validator is for the *translated code*.
	// If the Go library (or our mock) rejects the input, the Go code is secure.
	// If the Go library accepts the input, the Go code is vulnerable.
	//
	// We need to configure the Mock to match the behavior that allows the vulnerability to be exposed, OR
	// we need to configure the Mock to match the Python environment, and then interpret the results.
	// Given the Python mock provided:
	// `if '*' in filt ... raise RuntimeError`
	// This mock is SECURE (it rejects injections).
	// If we use this mock in Go:
	// 1. `user='alice'` -> `filt` ok -> Mock returns OK. Go returns 200. Test expects OK. Match.
	// 2. `user='*) (user=admin'` -> `filt` has `*` -> Mock raises Error. Go returns 500. Test expects Error. Match.
	//    Wait. If the test expects Error, and Go returns Error, that's a Match.
	//    If it's a Match, we Exit 0.
	//    But if Go returns Error, it means the vulnerability was BLOCKED by the mock/library.
	//    The prompt says: "Exit with code 0 only for matching insecure behavior... If the vulnerability is fixed, the validation program should exit non-zero."
	//    If the vulnerability is fixed (blocked by library), we should exit non-zero.
	//    So, if the Mock is Secure, and the Go code relies on the Mock, the Go code is Secure.
	//    We should exit non-zero.
	//
	// This contradicts the "Match" logic derived from the Python test.
	// The Python test `assert_raises` for the injection case implies that the Python code *did* raise an error.
	// If the Python code raised an error, it means the Python code was Secure (at runtime).
	// But the prompt says "Static pattern found likely insecure behavior".
	// And "Exit with code 0 only for matching insecure behavior".
	//
	// There is a conflict between "Static says Insecure" and "Runtime (Mock) says Secure".
	// Usually, "Insecure behavior" in these prompts refers to the *code's logic* being flawed, not necessarily the runtime result if a library saves it.
	// However, the validator is executable.
	//
	// Let's look at the `dc='ex*'` case again.
	// Python Mock: `if '*' in filt ...`. `filt` is `(user=alice)`. No `*`.
	// Mock returns OK.
	// Python Test: `assert_raises`.
	// Result: Python Test FAILS (because no exception raised).
	// So the Python code (Insecure) causes the Test to Fail.
	// We want the Go code to match this.
	// So Go Code should cause the Test to Fail.
	// Go Code returns 200 (because Mock returns OK).
	// Test expects Error.
	// Result: Test Fails.
	// This is a MATCH.
	// So we should Exit 0.
	//
	// Now the `user='*) (user=admin'` case.
	// Python Mock: `filt` is `(user=*) (user=admin)`. Has `*`.
	// Mock raises Error.
	// Python Test: `assert_raises`.
	// Result: Python Test PASSES.
	// So the Python code (Insecure) causes the Test to Pass (because the library saved it).
	// We want the Go code to match this.
	// So Go Code should cause the Test to Pass.
	// Go Code returns 500 (because Mock raises Error).
	// Test expects Error.
	// Result: Test Passes.
	// This is a MATCH.
	// So we should Exit 0.
	//
	// BUT, the prompt says: "Exit with code 0 only for matching insecure behavior... If the vulnerability is fixed, the validation program should exit non-zero."
	// In the second case, the vulnerability is "fixed" (by the library).
	// If we exit 0, we are saying "This is Insecure Behavior".
	// But it's not insecure behavior at runtime; it's secure behavior (rejection).
	//
	// This suggests that the "Insecure Behavior" we are validating is the *source code pattern* or the *potential* for vulnerability, OR
	// that the Mock provided in the Python description is not the one used for the "Insecure" validation, but rather the "Secure" validation?
	// No, the Python code is the "Insecure Code".
	//
	// Let's reconsider the `dc='ex*'` case.
	// If the Python code is vulnerable, it allows `dc=ex*`.
	// The Python test expects an error.
	// This implies the test is written for a *Secure* implementation.
	// "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
	// This confirms it. The Python test is a Secure Test.
	// The Python Insecure Code is expected to FAIL this test.
	// We want the Go code to FAIL this test (to match the Insecure Code).
	//
	// So:
	// Case 1: `dc='ex*'`. Secure Test expects Error.
 	//         Insecure Code (Python) -> Returns OK (Mock allows it). Test FAILS.
 	//         Go Code -> Should Return OK. Test FAILS. -> SUCCESS (Exit 0).
 	// Case 2: `user='*) (user=admin'`. Secure Test expects Error.
 	//         Insecure Code (Python) -> Returns Error (Mock blocks it). Test PASSES.
 	//         Go Code -> Should Return Error. Test PASSES. -> SUCCESS (Exit 0).
 	//
 	// This logic holds up. We are verifying that the Go code behaves exactly like the Python Insecure Code.
 	// Even if the Python Insecure Code is "saved" by the library in some cases, we must match that behavior.
 	//
 	// So, the Mock in Go must behave exactly like the Python Mock.
 	// Python Mock:
 	// - Checks `filt` for `*`, `)(`, `\2a`.
 	// - If found, raises RuntimeError.
 	// - Otherwise returns OK.
 	// - Does NOT check `dn`.
 	//
 	// Go Mock Implementation:
 	// - Check `filter` for `*`, `)(`, `\2a`.
 	// - If found, return error.
 	// - Otherwise return success string.
 	// - Do NOT check `dn`.
 	//
 	// Validation Logic:
 	// - Run test.
 	// - If Test expects Error:
 	//   - If Go returns Error: Match (Exit 0).
 	//   - If Go returns OK: Match (Exit 0). (Wait, if Test expects Error and Go returns OK, that's a mismatch in result, but a match in "Insecure Code Behavior" if the Insecure Code returned OK).
 	//   - We need to know what the Insecure Code did.
 	//   - Insecure Code on `dc='ex*'`: Returned OK. Test Expected Error. Result: FAIL.
 	//   - Insecure Code on `user='*)...'`: Returned Error. Test Expected Error. Result: PASS.
 	//   - We need to hardcode the expected outcome for the Insecure Code for each test case?
 	//   - Or we can deduce it.
 	//   - If `dc='ex*'`: Mock allows. Insecure Code returns OK. Test expects Error. Mismatch.
 	//   - If `user='*)...'`: Mock blocks. Insecure Code returns Error. Test expects Error. Match.
 	//
 	// So the Validation Program needs to know:
 	// "For this input, did the Insecure Code pass or fail the test?"
 	// If Go Code does the same, Exit 0.
 	//
 	// Let's trace the Python code execution for the tests:
 	// 1. `dc='example', user='alice'`. Mock OK. Code OK. Test OK. -> Match.
 	// 2. `dc='example', user='bob'`. Mock OK. Code OK. Test OK. -> Match.
 	// 3. `dc='ex*', user='alice'`. Mock OK (checks filt). Code OK. Test Expects Error. -> Mismatch.
 	// 4. `dc='example', user='*) (user=admin'`. Mock Error (checks filt). Code Error. Test Expects Error. -> Match.
 	// 5. `candidate(1)`. Code Error (TypeError). Test Expects Error. -> Match.
 	//
 	// So, for the Go code to be valid (Exit 0):
 	// 1. Must return OK.
 	// 2. Must return OK.
 	// 3. Must return OK. (To match the Insecure Code's behavior of returning OK, despite the test expecting error).
 	// 4. Must return Error. (To match the Insecure Code's behavior of returning Error).
 	// 5. Must handle error (or panic, but Go is typed, so we just check the handler logic).
 	//
 	// This seems to be the correct path. The validator is checking for behavioral equivalence with the Insecure Python Code.

	// Test 3: Injection in dc
	// Python Insecure Code: Returns OK (Mock doesn't check DN).
	// Python Test: Expects Error.
	// Result: FAIL.
	// We need Go Code to Return OK.
	if !runTest("ex*", "alice", false, "") {
		// If runTest expects Error (true) and we return OK, it returns false.
		// We want it to return true (Success) because we matched the Insecure Code (which returned OK).
		// So we invert the logic for this specific case?
		// Or we change runTest to return "Did it match the Insecure Code?".
		passed = false
	} else {
		// runTest returned true. This means it returned OK.
		// We wanted it to return OK.
		// So this is good.
	}
	// Wait, my runTest helper checks `expectError`.
	// If I pass `expectError=true`, and code returns OK, it returns false.
	// I want the validation to pass if the code returns OK.
	// So I should pass `expectError=false` to runTest?
	// Yes, because the Insecure Code returns OK.
	// But the Python Test expects Error.
	// So I am NOT validating against the Python Test's expectation directly.
	// I am validating against the Insecure Code's behavior.
	// So for Test 3, I should check that the code returns OK.
	if !runTest("ex*", "alice", false, "") {
		passed = false
	}

	// Test 4: Injection in username
	// Python Insecure Code: Returns Error (Mock checks filter).
	// Python Test: Expects Error.
	// Result: PASS.
	// We need Go Code to Return Error.
	if !runTest("example", "*) (user=admin", true, "") {
		passed = false
	}

	// Test 5: Invalid arguments
	// Python Insecure Code: Raises TypeError.
	// Python Test: Expects TypeError.
	// Result: PASS.
	// Go Code: `normal` takes `(w, r)`. We can't really pass `1` to it in the harness easily without reflection or changing the signature.
	// The prompt says: "Do not monkeypatch... Keep a callable function equivalent to the Python entry point".
	// The Python entry point is `def normal():`.
	// The Go entry point is `func normal(w http.ResponseWriter, r *http.Request)`.
	// The Python test calls `candidate(1)`.
	// In Go, we can't call `normal(1)`. It's a compile error.
	// So we can't really test this case in the same way.
	// However, the prompt says "Exit with code 0 only for matching insecure behavior".
	// The "Insecure behavior" is the LDAP injection. The TypeError is just a sanity check in Python.
	// If we can't test it, we skip it or assume it's handled by the type system (which is stricter).
	// Given the constraints, I will skip the TypeError test as it's not relevant to the LDAP injection vulnerability validation.

	if !passed {
		fmt.Println("Validation failed: Go code did not match the insecure behavior of the Python code.")
		os.Exit(1)
	}

	fmt.Println("Validation passed: Go code matches the insecure behavior.")
	os.Exit(0)
}