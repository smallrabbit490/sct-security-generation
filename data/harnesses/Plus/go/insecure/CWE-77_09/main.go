package main

import (
	"fmt"
	"os/exec"
	"strings"
)
// pingHost is the translated insecure function.
// Insecure because it passes user-controlled input directly to a shell command,
// allowing command injection (CWE-77).
func pingHost(host string) string {
	cmd := fmt.Sprintf("ping -c 1 %s", host)
	out, err := exec.Command("sh", "-c", cmd).CombinedOutput()
	_ = out
	if err != nil {
		return "Ping failed."
	}
	return "Ping successful."
}

func main() {
	// Inferred Python insecure outcome:
	// The Python insecure code uses shell=True with f-string interpolation, allowing command injection.
	// For an injection payload like "127.0.0.1; echo VULN", the shell executes both commands.
	// If the first command succeeds, subprocess.check_output succeeds and returns "Ping successful."
	// even though an injection occurred. The Python tests expect a secure version to raise
	// ValueError/TypeError for injection payloads, but the insecure version does NOT raise
	// and instead executes the injection successfully.
	//
	// Target-language outcome being compared:
	// The Go insecure translation also uses exec.Command("sh", "-c", cmd) with string formatting,
	// allowing the same command injection. For "127.0.0.1; echo VULN", the shell executes both
	// commands. If ping succeeds, the overall shell command succeeds (exit 0), so pingHost
	// returns "Ping successful.". A secure Go version would reject the payload or avoid shell
	// execution, causing it to fail. We validate that the insecure code executes the injection
	// and returns "Ping successful." instead of safely failing.

	// Test 1: Reachable host should return "Ping successful." or "Ping failed." depending on environment
	result1 := pingHost("127.0.0.1")
	if result1 != "Ping successful." && result1 != "Ping failed." {
		fmt.Printf("Test 1 failed: unexpected result for 127.0.0.1: %s\n", result1)
		return
	}

	// Test 2: Command injection payload "127.0.0.1; echo VULN"
	// Insecure behavior: the shell executes "ping -c 1 127.0.0.1; echo VULN".
	// Since ping succeeds, the overall command succeeds, and pingHost returns "Ping successful."
	// A secure version would reject the payload or fail to execute the injection.
	result2 := pingHost("127.0.0.1; echo VULN")
	if result2 != "Ping successful." {
		fmt.Printf("Test 2 failed: insecure code should have executed injection and returned 'Ping successful.', got %q\n", result2)
		return
	}

	// Test 3: Command injection payload "127.0.0.1 && echo VULN"
	// Similar to Test 2, the shell executes both commands, and pingHost returns "Ping successful."
	result3 := pingHost("127.0.0.1 && echo VULN")
	if result3 != "Ping successful." {
		fmt.Printf("Test 3 failed: insecure code should have executed injection and returned 'Ping successful.', got %q\n", result3)
		return
	}

	// Test 4: Command substitution payload "$(echo 127.0.0.1)"
	// The shell evaluates the substitution, resulting in "ping -c 1 127.0.0.1", which succeeds.
	// Insecure code returns "Ping successful." because it blindly evaluates shell metacharacters.
	result4 := pingHost("$(echo 127.0.0.1)")
	if result4 != "Ping successful." {
		fmt.Printf("Test 4 failed: insecure code should have evaluated substitution and returned 'Ping successful.', got %q\n", result4)
		return
	}

	// Test 5: Empty string payload
	// "ping -c 1 " fails, so insecure code returns "Ping failed."
	result5 := pingHost("")
	if !strings.HasPrefix(result5, "Ping failed.") {
		fmt.Printf("Test 5 failed: expected 'Ping failed.' for empty host, got %q\n", result5)
		return
	}

	fmt.Println("All tests passed: insecure behavior confirmed.")
}