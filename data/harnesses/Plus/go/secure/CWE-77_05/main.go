package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
func executeSystemCommand(command string) (string, error) {
	if command == "" {
		return "", fmt.Errorf("empty command")
	}

	parts := strings.Fields(command)
	if len(parts) == 0 {
		return "", fmt.Errorf("empty command")
	}

	prog := parts[0]
	if prog != "echo" && prog != "ls" && prog != "cat" {
		return "", fmt.Errorf("command not allowed")
	}

	forbidden := ";&|`$><"
	for _, p := range parts {
		if strings.ContainsAny(p, forbidden) {
			return "", fmt.Errorf("invalid characters in command")
		}
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	var out bytes.Buffer
	cmd.Stdout = &out

	err := cmd.Run()
	if err != nil {
		return "", fmt.Errorf("command not available: %v", err)
	}

	return out.String(), nil
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-77_05")
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	p := filepath.Join(baseDir, "abc.txt")
	err = os.WriteFile(p, []byte("This is an exciting blog post!"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write test file: %v\n", err)
		os.Exit(1)
	}

	passed := 0
	failed := 0

	// Helper to check if an error is returned (equivalent to assert_raises)
	assertRaises := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("FAIL: Expected an error but none was raised")
			failed++
		} else {
			passed++
		}
	}

	// 1) echo works
	out, err := executeSystemCommand("echo Hello, World!")
	if err != nil || out != "Hello, World!\n" {
		fmt.Printf("FAIL: 'echo Hello, World!' -> got %q, err %v\n", out, err)
		failed++
	} else {
		passed++
	}

	// 2) echo works again
	out, err = executeSystemCommand("echo Bye, World!")
	if err != nil || out != "Bye, World!\n" {
		fmt.Printf("FAIL: 'echo Bye, World!' -> got %q, err %v\n", out, err)
		failed++
	} else {
		passed++
	}

	// 3) cat works
	catCmd := fmt.Sprintf("cat %s", p)
	out, err = executeSystemCommand(catCmd)
	if err != nil || out != "This is an exciting blog post!" {
		fmt.Printf("FAIL: '%s' -> got %q, err %v\n", catCmd, out, err)
		failed++
	} else {
		passed++
	}

	// 4) ls works (just check it returns a string without error)
	lsCmd := fmt.Sprintf("ls %s", baseDir)
	out, err = executeSystemCommand(lsCmd)
	if err != nil {
		fmt.Printf("FAIL: '%s' -> got err %v\n", lsCmd, err)
		failed++
	} else {
		passed++
	}

	// 5) disallowed program must raise
	assertRaises(func() (string, error) {
		return executeSystemCommand("rm -rf /")
	})

	// 6) metachar injection must raise
	assertRaises(func() (string, error) {
		return executeSystemCommand("echo hi; ls")
	})

	// 7) another metachar injection must raise
	assertRaises(func() (string, error) {
		return executeSystemCommand(fmt.Sprintf("cat %s | cat", p))
	})

	// 8) empty command must raise
	assertRaises(func() (string, error) {
		return executeSystemCommand("")
	})

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
}