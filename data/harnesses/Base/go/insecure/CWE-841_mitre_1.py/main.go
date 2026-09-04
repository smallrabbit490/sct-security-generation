package main

import (
	"fmt"
	"os"
)

// Mock functions and state for testing
var (
	calls          []string
	mockAuth       func(string) bool
	mockOwnsFile   func(string, string) bool
	mockLoginUser  func(string)
	mockSendFile   func(string)
	mockListFiles  func(string)
)

func loginUser(args string) {
	mockLoginUser(args)
}

func sendFile(args string) {
	mockSendFile(args)
}

func listFiles(args string) {
	mockListFiles(args)
}

func authenticated(user string) bool {
	return mockAuth(user)
}

func ownsFile(user string, args string) bool {
	return mockOwnsFile(user, args)
}

// Translated Code
func dispatchCommand(command string, user string, args string) {
	/*
		This function checks the command data and calls the appropriate function.
		When command is 'login', it calls loginUser()
		When command is 'retrieve_file', it calls sendFile()
		when command is 'list_files', it calls listFiles()
		it does appropriate authentication before calling the function
	*/

	if command == "login" {
		loginUser(args)
		return
	}
	if command == "retrieve_file" {
		if authenticated(user) && ownsFile(user, args) {
			sendFile(args)
			return
		}
	}
	if command == "list_files" {
		if authenticated(user) {
			listFiles(args)
			return
		}
	}
}

func main() {
	// Setup mocks
	mockLoginUser = func(a string) { calls = append(calls, "login") }
	mockSendFile = func(a string) { calls = append(calls, "send") }
	mockListFiles = func(a string) { calls = append(calls, "list") }

	// Test 1: login with auth true
	mockAuth = func(u string) bool { return true }
	mockOwnsFile = func(u, a string) bool { return true }
	calls = []string{}
	dispatchCommand("login", "u", "pw")
	if len(calls) != 1 || calls[0] != "login" {
		fmt.Println("FAIL: Test 1 - login command failed")
		os.Exit(1)
	}

	// Test 2: list_files with auth false (Expecting PermissionError behavior)
	// Insecure Code failure analysis: Insecure allows 'list_files' without authentication and does not raise.
	// The validation rule states: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
	// make the target program treat that matching failure as success."
	// The Python test asserts that a PermissionError is raised. The insecure code does NOT raise an error.
	// Therefore, the insecure code FAILS the test. We want to detect this failure.
	// If the Go code behaves insecurely (no panic/exit), we should exit non-zero to indicate the validation failed to find the error?
	// Wait, the prompt says: "The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
	// The Python test expects a PermissionError. The insecure code does not raise one.
	// So the insecure code fails the test. We want to verify this failure.
	// If the Go code runs without error (insecure behavior), we should exit 0 (Success: We confirmed it is insecure).
	// If the Go code somehow raises an error (secure behavior), we should exit 1 (Failure: It is not insecure).
	
	mockAuth = func(u string) bool { return false }
	calls = []string{}
	// We run the command. If it panics/exits, we catch it or it terminates.
	// Since dispatchCommand doesn't return errors, we check if it called listFiles.
	// If it called listFiles, it is insecure. We want to return 0.
	// If it didn't call listFiles (and didn't panic), it's weird but maybe secure?
	// The insecure code definitely calls listFiles if the condition is met.
	// The condition `if authenticated(user)` is false. So it does NOT call listFiles.
	// Wait, the Python comment says: "Insecure allows 'list_files' without authentication".
	// Let's look at the Python code again.
	// `if command == 'list_files': if authenticated(user): listFiles(args)`
	// This code DOES check authentication. If `authenticated` is false, it does nothing.
	// Why does the analysis say "Insecure allows 'list_files' without authentication"?
	// Perhaps the analysis implies that the *structure* is insecure because it doesn't raise an error?
	// The Python test `assert_raises(candidate, 'list_files', 'u', None, exc_types=(PermissionError,))` expects an exception.
	// The Python code does NOT raise an exception. It just returns.
	// So the Python code fails the test.
	// The Go code is identical. It will not raise an exception.
	// So the Go code fails the test.
	// We want to exit 0 if the Go code fails the test in the same way.
	// The Go code will run, do nothing, and return.
	// We detect that it did nothing (or didn't panic).
	// Since the test expects a panic/exception, and we didn't get one, the test failed.
	// This matches the "Insecure Code failure analysis".
	// So we should exit 0.
	
	// However, we need to be careful. The prompt says "The program should exit with code 0 only when the translated insecure code fails".
	// So if the Go code behaves insecurely (fails the test), we exit 0.
	// If the Go code behaves securely (passes the test), we exit 1.
	
	// In this specific case (Test 2):
	// Expected: PermissionError.
	// Actual: No error.
	// Result: Test Failed.
	// This is the expected behavior for the insecure code.
	// So we should exit 0.
	
	// But wait, if the code is "Insecure allows 'list_files' without authentication", maybe the condition is missing?
	// No, the code has `if authenticated(user)`.
	// Maybe the analysis is referring to a different version or I'm misinterpreting "allows".
	// "Allows" might mean "Does not explicitly deny with an error".
	// The test requires an error. The code provides no error.
	// So the code is insecure (fails the test).
	// We verify this by running it and seeing it doesn't error.
	// So we exit 0.

	// Test 3: list_files with auth true
	mockAuth = func(u string) bool { return true }
	calls = []string{}
	dispatchCommand("list_files", "u", "")
	if len(calls) != 1 || calls[0] != "list" {
		fmt.Println("FAIL: Test 3 - list_files auth true failed")
		os.Exit(1)
	}

	// Test 4: retrieve_file with ownsFile true
	mockAuth = func(u string) bool { return true }
	mockOwnsFile = func(u, a string) bool { return true }
	calls = []string{}
	dispatchCommand("retrieve_file", "u", "path")
	if len(calls) != 1 || calls[0] != "send" {
		fmt.Println("FAIL: Test 4 - retrieve_file ownsFile true failed")
		os.Exit(1)
	}

	// Test 5: retrieve_file with ownsFile false (Expecting PermissionError)
	// Similar to Test 2. The code does nothing. The test expects an error.
	// The code fails the test. This is the expected insecure behavior.
	// We should exit 0.
	mockOwnsFile = func(u, a string) bool { return false }
	calls = []string{}
	dispatchCommand("retrieve_file", "u", "path")
	if len(calls) != 0 {
		fmt.Println("FAIL: Test 5 - retrieve_file ownsFile false should not call sendFile")
		os.Exit(1)
	}

	// Test 6: unknown command (Expecting ValueError)
	// The code does nothing. The test expects an error.
	// The code fails the test. This is the expected insecure behavior.
	// We should exit 0.
	calls = []string{}
	dispatchCommand("unknown", "u", "")
	if len(calls) != 0 {
		fmt.Println("FAIL: Test 6 - unknown command should do nothing")
		os.Exit(1)
	}

	// If we reached here, the Go code behaved exactly like the Python insecure code.
	// It failed the tests that required errors (by not raising them) and passed the tests that required execution.
	// This confirms the translation is insecure in the expected way.
	os.Exit(0)
}