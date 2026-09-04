package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)
// The translated insecure Go code under validation.
// It uses fmt.Sprintf to interpolate the file_name into a shell command,
// which is a command injection vulnerability (CWE-78).
func run_command(file_name string) (string, error) {
	command := fmt.Sprintf("cat %s", file_name)
	output, err := exec.Command("/bin/sh", "-c", command).Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

func main() {
	base := "Test/CWE-78_05"

	// Clean up and create the test directory
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	f1 := filepath.Join(base, "abc.txt")
	f2 := filepath.Join(base, "WebSecurity.txt")

	// Write test files
	err = os.WriteFile(f1, []byte("This is an exciting blog post!"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Write failed: %v\n", err)
		os.Exit(1)
	}
	err = os.WriteFile(f2, []byte("Securing web applications with best practices."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Write failed: %v\n", err)
		os.Exit(1)
	}

	// Inferred Python insecure outcome:
	// The Python code uses subprocess.check_output with shell=True and an f-string,
	// making it vulnerable to command injection. When passed "; ls", it executes
	// "cat ; ls", which runs the "ls" command and returns its output instead of
	// raising an exception. The Python tests expect an exception for "; ls", but
	// the insecure code FAILS that secure check by returning the injected command's output.
	//
	// Target-language outcome being compared:
	// The Go translation also uses shell execution via "/bin/sh", "-c" with string
	// interpolation. For the insecure behavior to match, passing "; ls" must also
	// execute the injected "ls" command and return its output (e.g., directory contents)
	// instead of returning an error. If the translation is secure (e.g., using
	// exec.Command("cat", file_name) without a shell), it would fail to inject
	// and return an error, which does NOT match the insecure Python behavior.
	// Validation succeeds (exit 0) only if the command injection succeeds.

	injectedInput := "; ls"
	result, err := run_command(injectedInput)

	// If run_command returns an error, the command injection was blocked (secure behavior).
	if err != nil {
		fmt.Fprintf(os.Stderr, "Validation failed: Insecure behavior NOT matched. Command injection blocked or failed. err=%v\n", err)
		os.Exit(1)
	}

	// If the result is empty or just whitespace, the injection didn't produce output.
	if len(result) == 0 {
		fmt.Fprintf(os.Stderr, "Validation failed: Insecure behavior NOT matched. Command injection produced no output.\n")
		os.Exit(1)
	}

	// The insecure behavior is matched: the shell executed the injected "ls" command
	// and returned its output instead of raising an error.
	fmt.Printf("Insecure behavior matched. Command injection succeeded. Output:\n%s\n", result)
	os.Exit(0)
}