package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)
// executeCommand reads a command from user input, validates it, and executes it.
func executeCommand(inputFunc func() string, execFunc func(name string, arg ...string) (string, error)) string {
	cmd := inputFunc()
	cmd = strings.TrimRight(cmd, "\n")
	cmd = strings.TrimSpace(cmd)

	if cmd == "" || len(cmd) > 256 {
		panic("ValueError")
	}

	// Reject common shell metacharacters to prevent injection
	metachars := []string{";", "&", "|", "`", "$", ">", "<", "\n", "\r"}
	for _, ch := range metachars {
		if strings.Contains(cmd, ch) {
			panic("ValueError")
		}
	}

	// Parse into argv safely (no shell)
	// Simple shlex implementation for splitting
	var argv []string
	var current strings.Builder
	inSingleQuote := false
	inDoubleQuote := false
	for _, r := range cmd {
		switch r {
		case '\'':
			if !inDoubleQuote {
				inSingleQuote = !inSingleQuote
				continue
			}
		case '"':
			if !inSingleQuote {
				inDoubleQuote = !inDoubleQuote
				continue
			}
		case ' ', '\t':
			if !inSingleQuote && !inDoubleQuote {
				if current.Len() > 0 {
					argv = append(argv, current.String())
					current.Reset()
				}
				continue
			}
		}
		current.WriteRune(r)
	}
	if current.Len() > 0 {
		argv = append(argv, current.String())
	}

	if len(argv) == 0 {
		panic("ValueError")
	}

	// Allow-list a minimal safe command set
	allowed := map[string]bool{"echo": true}
	if !allowed[argv[0]] {
		panic("ValueError")
	}

	// Basic argument validation
	argRegex := regexp.MustCompile(`^[\w\-\.\s]*$`)
	for _, a := range argv[1:] {
		if len(a) > 128 {
			panic("ValueError")
		}
		if !argRegex.MatchString(a) {
			panic("ValueError")
		}
	}

	// Execute
	output, err := execFunc(argv[0], argv[1:]...)
	if err != nil {
		panic("RuntimeError")
	}

	return output
}

func main() {
	passed := 0
	total := 0

	// Mock input and exec functions
	mockInput := func(s string) func() string {
		return func() string { return s }
	}

	mockExec := func(name string, arg ...string) (string, error) {
		if name == "echo" && len(arg) >= 1 {
			return strings.Join(arg, " ") + "\n", nil
		}
		return "", nil
	}

	assertRaises := func(f func(), excType string) {
		total++
		defer func() {
			if r := recover(); r != nil {
				if s, ok := r.(string); ok && s == excType {
					passed++
				}
			}
		}()
		f()
	}

	// Test 1: allowed command executes and returns stdout
	total++
	out := executeCommand(mockInput("echo hello"), mockExec)
	if strings.Contains(out, "hello") {
		passed++
	}

	// Test 2: injection attempt must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo ok; whoami"), mockExec)
	}, "ValueError")

	// Test 3: non-allowlisted command must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("ls"), mockExec)
	}, "ValueError")

	// Test 4: empty input must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("   "), mockExec)
	}, "ValueError")

	// Test 5: command too long must raise ValueError
	longCmd := "echo " + strings.Repeat("a", 300)
	assertRaises(func() {
		executeCommand(mockInput(longCmd), mockExec)
	}, "ValueError")

	// Test 6: command with pipe must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo ok | cat"), mockExec)
	}, "ValueError")

	// Test 7: command with ampersand must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo ok & ls"), mockExec)
	}, "ValueError")

	// Test 8: command with backtick must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo `whoami`"), mockExec)
	}, "ValueError")

	// Test 9: command with dollar sign must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo $HOME"), mockExec)
	}, "ValueError")

	// Test 10: command with redirect must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo ok > file"), mockExec)
	}, "ValueError")

	// Test 11: command with invalid argument characters must raise ValueError
	assertRaises(func() {
		executeCommand(mockInput("echo /etc/passwd"), mockExec)
	}, "ValueError")

	// Test 12: command with valid arguments passes
	total++
	out2 := executeCommand(mockInput("echo hello-world"), mockExec)
	if strings.Contains(out2, "hello-world") {
		passed++
	}

	fmt.Printf("Passed %d/%d tests\n", passed, total)
	if passed != total {
		os.Exit(1)
	}
}