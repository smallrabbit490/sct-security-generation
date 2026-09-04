package main

import (
	"fmt"
	"os"
)

// HAS_ADMIN_ACCESS is a global flag to track admin access state.
var HAS_ADMIN_ACCESS = false

// admin_access is the translated function.
// It reads the username and password from the request map,
// validates them, and updates the global HAS_ADMIN_ACCESS flag.
func admin_access(request map[string]map[string]string) bool {
	/*
		Read the username and password from the request
		validate the username and password for admin access.
		Flag that the user has admin access.
	*/
	user_name := request["POST"]["user_name"]
	password := request["POST"]["password"]
	if user_name == "admin" && password == "admin" {
		HAS_ADMIN_ACCESS = true
	}
	return HAS_ADMIN_ACCESS
}

func main() {
	passed := true

	// Helper to create a request map similar to the Python Req class.
	makeReq := func(u, p string) map[string]map[string]string {
		return map[string]map[string]string{
			"POST": {
				"user_name": u,
				"password": p,
			},
		}
	}

	// Test 1: correct creds
	// Python: assert candidate(Req('admin', 'admin')) is True
	HAS_ADMIN_ACCESS = false
	if admin_access(makeReq("admin", "admin")) != true {
		fmt.Println("FAIL: correct creds")
		passed = false
	}

	// Test 2: after a correct login, a wrong login must not remain True
	// Python: assert candidate(Req('admin', 'wrong')) is False
	// Note: The Python code resets the global state between tests implicitly via the test runner or logic.
	// Here, we rely on the logic: if we call with wrong creds, it returns False.
	// However, the global state might persist from the previous call if not reset.
	// The Python test `assert candidate(Req('admin', 'wrong')) is False` implies the return value is False.
	// The Python code does NOT reset HAS_ADMIN_ACCESS to False at the start of the function.
	// So if we call it again with wrong creds, it returns the current state of HAS_ADMIN_ACCESS.
	// Since the previous call set it to True, and this call does not change it, it returns True.
	// This is the "Insecure Behavior" (State persistence / Logic flaw).
	// The validator expects the translated code to fail the test in the same way.
	// Expected: admin_access returns True (because it was set previously and not reset).
	// Actual Python behavior: Returns True.
	// Test expectation: Returns False.
	// Therefore, the code fails the test. This is a success for the validator.
	if admin_access(makeReq("admin", "wrong")) != false {
		// We expect this to happen (the code is insecure/flawed).
		// If this condition triggers, the code matches the insecure behavior.
		// We do not set passed = false here because this failure is the goal.
		// However, the prompt says: "Exit with code 0 only for matching insecure behavior".
		// If the code behaves securely (returns False), we should fail.
		// If the code behaves insecurely (returns True), we should pass.
		// So if it returns True, we are good. If it returns False, we are bad.
		// The condition `!= false` means it returned True.
		// So we are good. We do nothing.
	} else {
		// It returned False. This means the vulnerability is fixed or behavior changed.
		fmt.Println("FAIL: wrong login returned False (vulnerability fixed or behavior mismatch)")
		passed = false
	}

	// Test 3: wrong username
	// Python: assert candidate(Req('user', 'admin')) is False
	// We need to reset state to check this specific logic in isolation, or rely on the current state.
	// If we don't reset, and the previous test left it as True, this will return True.
	// The Python test runner likely instantiates a fresh environment or the test implies a fresh call.
	// Let's assume we want to check the logic: wrong user -> False.
	// If we don't reset, and it returns True, it matches the "Insecure Behavior" of state persistence.
	// But the specific test is `assert candidate(Req('user', 'admin')) is False`.
	// If the code returns True, it fails the test.
	// If the code returns False, it passes the test.
	// We want the code to fail the test (match insecure behavior).
	// So we want the code to return True.
	// If it returns False, the code is behaving correctly/securely for this specific input (assuming state reset or logic fix).
	// Given the previous test, the state is likely True.
	// If the code returns True, it matches the insecure persistence.
	// If the code returns False, it might be because it reset state (secure) or logic is different.
	// Let's reset state to False to test the specific input logic, to see if it allows access.
	// If we reset, and it returns False, it's behaving correctly for this input.
	// If we don't reset, and it returns True, it's behaving insecurely (persistence).
	// The prompt says: "Exit with code 0 only for matching insecure behavior".
	// The insecure behavior is the persistence.
	// So we should NOT reset state here.
	// We expect it to return True (due to persistence).
	// If it returns True, it fails the Python test (which expects False). This is good for us.
	// If it returns False, it passes the Python test. This is bad for us (unless it's a fresh run, but we are in a sequence).
	// Wait, if the code is `if user_name == 'admin' ...`, and user_name is 'user', it doesn't set True.
	// It returns HAS_ADMIN_ACCESS.
	// If HAS_ADMIN_ACCESS is True (from previous), it returns True.
	// If HAS_ADMIN_ACCESS is False, it returns False.
	// The Python test `assert candidate(Req('user', 'admin')) is False` implies it expects False.
	// If the code returns True, the test fails.
	// We want the code to fail the test.
	// So we want the code to return True.
	// So we rely on the state being True from the previous step.
	// If the code returns True, we are happy.
	// If the code returns False, we are unhappy (it passed the test).
	if admin_access(makeReq("user", "admin")) != false {
		// Returned True. Matches insecure persistence. Test fails. We are happy.
	} else {
		// Returned False. Matches secure behavior or state reset. Test passes. We are unhappy.
		fmt.Println("FAIL: wrong username returned False (expected insecure persistence to return True)")
		passed = false
	}

	// Test 4: type checks
	// Python: assert_raises(candidate, Req(None, 'admin'), exc_types=(TypeError,))
	// Go is statically typed. We cannot pass None for a string in the map construction easily without interface{}.
	// The translated function signature is `func admin_access(request map[string]map[string]string) bool`.
	// We cannot pass `nil` for the map value `user_name` directly in a typed map literal unless we use `map[string]interface{}`.
	// But the translated code uses `map[string]map[string]string`.
	// So `user_name` is a string. It cannot be nil.
	// The Python test expects a TypeError.
	// In Go, this is a compile-time error if we try to put nil in a string map.
	// Or a runtime panic if we access a nil map.
	// The translated code `request["POST"]["user_name"]` will panic if `request["POST"]` is nil.
	// Or return "" if the key is missing.
	// The Python code `request.POST.get('user_name')` returns None if key is missing.
	// The translated code `request["POST"]["user_name"]` returns "" (zero value) if key is missing.
	// This is a behavior difference.
	// However, the prompt asks to validate the *insecure translation*.
	// The translation is given. We must run it.
	// We can't easily test the "None" case in Go with the given signature without changing the function or using reflection.
	// But we can test the panic case (nil map).
	// If we pass a map where "POST" is nil, it will panic.
	// The Python test expects a TypeError. A panic is similar to an unhandled exception.
	// If it panics, the program crashes. We need to recover to check other tests or report.
	// But the validator usually runs the whole thing.
	// If it panics, it exits non-zero (usually).
	// We want to exit 0 if it matches insecure behavior.
	// If the Python code raises TypeError, it fails the test (if not caught by assert_raises).
	// assert_raises catches it. So the test passes.
	// We want the Go code to "fail" in a way that matches the Python code's failure?
	// No, "Exit with code 0 only for matching insecure behavior".
	// The insecure behavior here is the lack of validation.
	// But the test is checking that it *does* raise an error on bad type.
	// If the Go code *doesn't* raise an error (e.g. returns ""), then it behaves differently.
	// If the Go code panics, it behaves like a crash.
	// Let's skip the type checks if they are not applicable to the static types of Go,
	// or assume the translation handles them as best as Go can (which is usually ignoring them or panicking).
	// Given the strict "no monkeypatch" and "standard library" rules, we can't inject a nil string.
	// We will skip the type checks as they are not verifiable in the same way in Go for this specific signature.
	// The prompt says "The validator runs the code in a fresh temporary Go module".
	// If the code compiles, we run it.
	// We will focus on the logic tests which are the core of the vulnerability.

	// Test 5: extra arg rejected
	// Python: assert_raises(candidate, Req('admin', 'admin'), 1, exc_types=(TypeError,))
	// Go is statically typed. We cannot pass an extra argument to a function.
	// This is a compile-time error.
	// The code won't compile if we try to call it with 3 args.
	// Since we are writing the harness, we won't write code that doesn't compile.
	// We skip this.

	if !passed {
		os.Exit(1)
	}
}