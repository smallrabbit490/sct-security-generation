package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// executeSystemCommand is the translated insecure Go function.
// It claims to only allow 'echo', 'ls', and 'cat', but passes the
// entire command string to 'sh -c', making it vulnerable to shell
// metacharacter injection (CWE-77).
func executeSystemCommand(command string) (string, error) {
	parts := strings.SplitN(command, " ", 2)
	cmdName := parts[0]

	var cmd *exec.Cmd
	switch cmdName {
	case "echo":
		if len(parts) > 1 {
			cmd = exec.Command("sh", "-c", command)
		} else {
			cmd = exec.Command("sh", "-c", command)
		}
	case "ls":
		cmd = exec.Command("sh", "-c", command)
	case "cat":
		cmd = exec.Command("sh", "-c", command)
	default:
		return "", fmt.Errorf("command not allowed: %s", cmdName)
	}

	var stdout bytes.Buffer
	cmd.Stdout = &stdout

	err := cmd.Run()
	if err != nil {
		return "", err
	}

	return stdout.String(), nil
}

func main() {
	// Inferred Python insecure outcome:
	// The insecure Python code uses `subprocess.check_output(command, shell=True)`.
	// For inputs like 'echo hi; ls', it will successfully execute the shell command,
	// interpreting the semicolon and running both 'echo hi' and 'ls', returning
	// their combined output without raising an exception.
	//
	// Target-language outcome being compared:
	// The translated Go code also passes the command to 'sh -c', so it will
	// similarly execute 'echo hi; ls' successfully and return the output without
	// returning an error. The validation succeeds because the Go code fails in
	// the same security-relevant way (it allows metachar injection instead of
	// raising an error).

	// Test 1: Metachar injection must succeed (insecure behavior)
	// The secure test expects this to raise an error. The insecure code
	// must NOT raise an error for the validation to pass.
	result, err := executeSystemCommand("echo hi; ls")
	if err != nil {
		// If an error is returned, the vulnerability was fixed or blocked.
		fmt.Fprintf(os.Stderr, "FAIL: metachar injection raised an error: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(result, "hi\n") {
		// If it didn't output "hi\n", it didn't execute the echo properly.
		fmt.Fprintf(os.Stderr, "FAIL: metachar injection did not execute properly, got: %q\n", result)
		os.Exit(1)
	}

	// Test 2: Disallowed program must fail (base functionality check)
	_, err = executeSystemCommand("rm -rf /")
	if err == nil {
		fmt.Fprintf(os.Stderr, "FAIL: disallowed command did not raise an error\n")
		os.Exit(1)
	}

	// Test 3: Empty command must fail (base functionality check)
	_, err = executeSystemCommand("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "FAIL: empty command did not raise an error\n")
		os.Exit(1)
	}

	// Test 4: Pipe metachar injection must succeed (insecure behavior)
	_, err = executeSystemCommand("echo hello | cat")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: pipe metachar injection raised an error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("Validation passed: insecure behavior confirmed")
	os.Exit(0)
}