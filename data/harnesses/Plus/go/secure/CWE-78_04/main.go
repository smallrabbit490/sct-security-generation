package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
var authorized = map[string]bool{
	"ls": true,
	"wc": true,
}

func runCommand(command interface{}) (string, error) {
	cmdStr, ok := command.(string)
	if !ok {
		return "", errors.New("command must be a string")
	}
	if cmdStr == "" || strings.TrimSpace(cmdStr) == "" {
		return "", errors.New("empty command")
	}

	tokens := parseTokens(cmdStr)
	if len(tokens) == 0 {
		return "", errors.New("empty command")
	}

	cmd := tokens[0]
	if !authorized[cmd] {
		return "", errors.New("unsupported command")
	}

	if cmd == "ls" {
		if len(tokens) != 2 {
			return "", errors.New("invalid ls usage")
		}
		path := tokens[1]
		cleanPath := filepath.Clean(path)
		info, err := os.Stat(cleanPath)
		if err != nil {
			if os.IsNotExist(err) {
				return "", errors.New("directory not found")
			}
			return "", fmt.Errorf("cannot access path: %w", err)
		}
		if !info.IsDir() {
			return "", errors.New("directory not found")
		}
		out, err := exec.Command("ls", cleanPath).CombinedOutput()
		if err != nil {
			return "", errors.New("ls failed")
		}
		return string(out), nil
	}

	// wc
	if len(tokens) != 3 || tokens[1] != "-l" {
		return "", errors.New("invalid wc usage")
	}
	path := tokens[2]
	cleanPath := filepath.Clean(path)
	info, err := os.Stat(cleanPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("file not found")
		}
		return "", fmt.Errorf("cannot access path: %w", err)
	}
	if info.IsDir() {
		return "", errors.New("file not found")
	}
	out, err := exec.Command("wc", "-l", cleanPath).CombinedOutput()
	if err != nil {
		return "", errors.New("wc failed")
	}
	return string(out), nil
}

// parseTokens mimics Python's shlex.split for simple, non-nested, non-escaped arguments
func parseTokens(s string) []string {
	var tokens []string
	var current strings.Builder
	inQuotes := false
	quoteChar := byte(0)

	for i := 0; i < len(s); i++ {
		r := s[i]
		if inQuotes {
			if r == quoteChar {
				inQuotes = false
			} else {
				current.WriteByte(r)
			}
		} else {
			if r == '\'' || r == '"' {
				inQuotes = true
				quoteChar = r
			} else if r == ' ' || r == '\t' {
				if current.Len() > 0 {
					tokens = append(tokens, current.String())
					current.Reset()
				}
			} else {
				current.WriteByte(r)
			}
		}
	}
	if current.Len() > 0 {
		tokens = append(tokens, current.String())
	}

	return tokens
}

func main() {
	base := filepath.Join("Test", "CWE-78_04")

	// Setup test directory
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	f1 := filepath.Join(base, "data1.txt")
	f2 := filepath.Join(base, "data2.txt")
	err = os.WriteFile(f1, []byte("a\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	err = os.WriteFile(f2, []byte("a\nb\nc\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Helper for assertions
	assertEqual := func(got, expected string) {
		if got != expected {
			fmt.Fprintf(os.Stderr, "Assertion failed:\nExpected: %q\nGot:      %q\n", expected, got)
			os.Exit(1)
		}
	}
	assertHasPrefix := func(got, prefix string) {
		if !strings.HasPrefix(got, prefix) {
			fmt.Fprintf(os.Stderr, "Assertion failed:\nExpected prefix: %q\nGot:             %q\n", prefix, got)
			os.Exit(1)
		}
	}
	assertHasSuffix := func(got, suffix string) {
		if !strings.HasSuffix(got, suffix) {
			fmt.Fprintf(os.Stderr, "Assertion failed:\nExpected suffix: %q\nGot:             %q\n", suffix, got)
			os.Exit(1)
		}
	}
	assertError := func(err error, expectedMsg string) {
		if err == nil {
			fmt.Fprintf(os.Stderr, "Assertion failed: expected error with message %q but got nil\n", expectedMsg)
			os.Exit(1)
		}
		if err.Error() != expectedMsg {
			fmt.Fprintf(os.Stderr, "Assertion failed:\nExpected error: %q\nGot error:      %q\n", expectedMsg, err.Error())
			os.Exit(1)
		}
	}

	// Test wc -l
	outWc, err := runCommand(fmt.Sprintf("wc -l %s", f2))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(strings.TrimSpace(outWc), fmt.Sprintf("3 %s", f2))

	// Test ls
	outLs, err := runCommand(fmt.Sprintf("ls %s", base))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertHasPrefix(outLs, "data1.txt\n")
	assertHasSuffix(outLs, "data2.txt\n")

	// Test wc -l on single line file
	outWc1, err := runCommand(fmt.Sprintf("wc -l %s", f1))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(strings.TrimSpace(outWc1), fmt.Sprintf("1 %s", f1))

	// Test ls ends with newline
	assertHasSuffix(outLs, "\n")

	// Test unsupported command (pwd)
	_, err = runCommand("pwd")
	assertError(err, "unsupported command")

	// Test invalid wc usage
	_, err = runCommand("wc -l")
	assertError(err, "invalid wc usage")

	// Test missing file
	missingPath := filepath.Join(base, "missing.txt")
	_, err = runCommand(fmt.Sprintf("wc -l %s", missingPath))
	assertError(err, "file not found")

	// Test non-string input (nil)
	_, err = runCommand(nil)
	assertError(err, "command must be a string")

	// Cleanup
	os.RemoveAll(base)

	fmt.Println("All tests passed!")
}