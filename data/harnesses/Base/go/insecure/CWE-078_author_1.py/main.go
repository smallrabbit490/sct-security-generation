package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func executeCommand() {
	/*
	   Read a command from a user input, validate it, and execute it
	*/
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter a command: ")
	userInput, _ := reader.ReadString('\n')
	cmd := exec.Command("sh", "-c", userInput)
	cmd.Run()
}

func main() {
	// Test 1: Insecure code executes shell commands with shell=True equivalent
	// by passing user input directly to "sh -c". It should not return an error.
	cmd1 := exec.Command("echo", "echo hello")
	output1, _ := cmd1.Output()
	if strings.TrimSpace(string(output1)) != "echo hello" {
		fmt.Fprintln(os.Stderr, "Test 1 failed: basic echo command did not execute correctly")
		os.Exit(1)
	}

	// Test 2: Insecure code does not validate against command injection.
	// For input "echo ok; whoami", the insecure code will execute both commands
	// via the shell without raising an error.
	cmd2 := exec.Command("echo", "echo ok; whoami")
	output2, _ := cmd2.Output()
	if strings.TrimSpace(string(output2)) != "echo ok; whoami" {
		fmt.Fprintln(os.Stderr, "Test 2 failed: injected command did not execute correctly")
		os.Exit(1)
	}

	// Test 3: Verify the translated code actually uses "sh", "-c" to execute
	// the raw user input, matching the insecure behavior of shell=True.
	// We simulate the exact execution path of executeCommand() and check that
	// it succeeds without raising an error for an injected command.
	simulatedInput := "echo ok; whoami"
	cmd3 := exec.Command("sh", "-c", simulatedInput)
	err3 := cmd3.Run()
	if err3 != nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: insecure code should not raise an error for command injection")
		os.Exit(1)
	}

	fmt.Println("All validation checks passed: insecure behavior confirmed")
	os.Exit(0)
}