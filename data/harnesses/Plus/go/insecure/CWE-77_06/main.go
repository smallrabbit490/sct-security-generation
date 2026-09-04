package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code uses subprocess.getoutput(f"mv {old_name} {new_name}"),
// which is vulnerable to command injection. When given an injection-like new_name
// such as "new_name.txt; rm -rf", the insecure Python code would execute the
// injected shell command instead of raising a ValueError. The Python tests expect
// a secure implementation to raise ValueError for such inputs, but the insecure
// code would fail this check by successfully executing the malicious shell command.
//
// Target-language outcome being compared:
// The translated Go code also uses shell execution via exec.Command("sh", "-c", ...),
// making it equally vulnerable to command injection. We validate this by providing
// an injection payload as the new_name. If the Go code is insecure, it will execute
// the shell command and create a file named "pwned". If the Go code is secure
// (e.g., using os.Rename and validating inputs), it will refuse the invalid
// filename and the "pwned" file will not be created. The validation succeeds
// (exits 0) only if the "pwned" file is created, confirming the insecure behavior.

func renameFile(oldName, newName string) string {
	command := fmt.Sprintf("mv %s %s", oldName, newName)
	cmd := exec.Command("sh", "-c", command)
	output, err := cmd.CombinedOutput()
	if err != nil {
		fmt.Fprintln(os.Stderr, string(output))
		os.Exit(1)
	}
	return string(output)
}

func main() {
	basePath := filepath.Join(os.TempDir(), "CWE-77_06_Go")
	os.RemoveAll(basePath)
	if err := os.MkdirAll(basePath, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base path: %v\n", err)
		os.Exit(2)
	}
	defer os.RemoveAll(basePath)

	initial := filepath.Join(basePath, "initial_report.txt")
	if err := os.WriteFile(initial, []byte("This is a test report."), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create initial file: %v\n", err)
		os.Exit(2)
	}

	// Injection payload: the shell will execute "touch pwned" as a separate command
	injectionName := "new_name.txt; touch " + filepath.Join(basePath, "pwned")

	// Call the vulnerable function. If it's insecure, it will execute the shell
	// injection and create the "pwned" file. If it's secure, it will reject the
	// invalid filename and the "pwned" file won't exist.
	renameFile(initial, injectionName)

	pwnedPath := filepath.Join(basePath, "pwned")
	if _, err := os.Stat(pwnedPath); err == nil {
		// The "pwned" file exists, meaning the shell injection was executed.
		// This matches the expected insecure behavior.
		fmt.Println("Insecure behavior confirmed: shell injection executed successfully.")
		os.Exit(0)
	} else if os.IsNotExist(err) {
		// The "pwned" file does not exist, meaning the injection was blocked.
		// The vulnerability is fixed, so the validation must fail (exit non-zero).
		fmt.Println("Secure behavior detected: shell injection was blocked.")
		os.Exit(1)
	} else {
		// Unexpected error checking the file
		fmt.Fprintf(os.Stderr, "Error checking pwned file: %v\n", err)
		os.Exit(2)
	}

	// Suppress unused variable warning for strings package
	_ = strings.TrimSpace("")
}