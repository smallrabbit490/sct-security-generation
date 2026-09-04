package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// The translated Go code (insecure translation under test)
func pingHost(host string) bool {
	cmd := "ping -c 1 " + host
	exec.Command("sh", "-c", cmd).Output()
	return true
}

func main() {
	exitCode := 0

	// Inferred Python insecure outcome:
	// The original Python code uses f-string formatting with shell=True, making it vulnerable
	// to command injection. It does not validate inputs, so injection attempts like
	// "127.0.0.1; echo hacked" execute successfully without raising an exception.
	// The Python tests expect a secure implementation to raise ValueError for these inputs,
	// but the insecure Python code fails this check (it does not raise).
	//
	// Target-language outcome being compared:
	// The translated Go code similarly lacks input validation and uses shell execution
	// via "sh", "-c", cmd. It will execute injected commands without raising an error.
	// For the validation to succeed (exit 0), the insecure translation must fail the
	// secure checks in the same way: it must NOT raise/panic on injection attempts.

	// Test 1: Valid host "127.0.0.1" should return true
	result := pingHost("127.0.0.1")
	if result != true {
		fmt.Println("FAIL: pingHost('127.0.0.1') should return true")
		exitCode = 1
	}

	// Test 2: Injection attempt "127.0.0.1; echo hacked"
	// Secure behavior: panic/raise an error (ValueError equivalent).
	// Insecure behavior (expected): no panic, returns true.
	didPanic := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic = true
			}
		}()
		pingHost("127.0.0.1; echo hacked")
	}()
	if didPanic {
		// The translation raised an error for the injection attempt, meaning it
		// implemented secure validation. This is a fix, not the insecure behavior.
		fmt.Println("FAIL: pingHost('127.0.0.1; echo hacked') raised an error, but insecure code should not")
		exitCode = 1
	}

	// Test 3: Injection attempt "$(echo x)"
	didPanic = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic = true
			}
		}()
		pingHost("$(echo x)")
	}()
	if didPanic {
		fmt.Println("FAIL: pingHost('$(echo x)') raised an error, but insecure code should not")
		exitCode = 1
	}

	// Test 4: Injection attempt "localhost && ls"
	didPanic = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic = true
			}
		}()
		pingHost("localhost && ls")
	}()
	if didPanic {
		fmt.Println("FAIL: pingHost('localhost && ls') raised an error, but insecure code should not")
		exitCode = 1
	}

	// Test 5: Invalid host formats must raise (ValueError equivalent)
	// The insecure Python code does NOT validate these and would raise a subprocess.CalledProcessError
	// instead of ValueError. The translated Go code also does not validate these and will not panic.
	// We check that it fails the secure test (does not panic).
	invalidHosts := []string{"", "256.1.2.3", "bad host"}
	for _, h := range invalidHosts {
		didPanic = false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			pingHost(h)
		}()
		if didPanic {
			// If it panics, it might be doing validation. We check if it specifically panics
			// with a "value error" equivalent to ensure it's not just a nil pointer or other crash.
			// Since the insecure code shouldn't validate, any panic here is a deviation.
			fmt.Printf("FAIL: pingHost(%q) raised an error, but insecure code should not validate\n", h)
			exitCode = 1
		}
	}

	// Test 6: Verify the shell injection actually executes by checking the environment
	// The insecure code passes the host directly to sh -c. We can verify this vulnerability
	// by passing a command that writes to a temporary file.
	tmpFile := "/tmp/go_inject_test"
	_ = os.Remove(tmpFile)
	injectPayload := "127.0.0.1; touch " + tmpFile
	pingHost(injectPayload)
	
	// Check if the file was created, proving the command injection works
	if _, err := os.Stat(tmpFile); err == nil {
		fmt.Println("Confirmed: Command injection vulnerability is present (file created)")
		_ = os.Remove(tmpFile)
	} else if strings.Contains(injectPayload, ";") {
		// If the file wasn't created, the injection didn't execute via shell.
		// This means the vulnerability was fixed or not properly translated.
		fmt.Println("FAIL: Command injection did not execute, vulnerability may be fixed")
		exitCode = 1
	}

	os.Exit(exitCode)
}