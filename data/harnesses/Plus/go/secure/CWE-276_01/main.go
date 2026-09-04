package main

import (
	"fmt"
	"os"
	"regexp"
	"syscall"
)
func createNotificationPipe(pipeName string) (string, error) {
	validPipeName := regexp.MustCompile(`^[A-Za-z0-9_-]+\.fifo$`)
	if !validPipeName.MatchString(pipeName) {
		return "", fmt.Errorf("invalid pipe_name")
	}

	directory := "Test/CWE-276_01"

	if err := os.MkdirAll(directory, 0700); err != nil {
		return "", fmt.Errorf("failed to create directory: %w", err)
	}

	if err := os.Chmod(directory, 0700); err != nil {
		_ = err
	}

	path := directory + string(os.PathSeparator) + pipeName

	info, err := os.Stat(path)
	if err == nil {
		if info.Mode()&os.ModeNamedPipe == 0 {
			return "", fmt.Errorf("path exists and is not a FIFO")
		}
		if err := os.Remove(path); err != nil {
			return "", fmt.Errorf("failed to remove existing FIFO: %w", err)
		}
	}

	err = syscall.Mkfifo(path, 0600)
	if err != nil {
		return "", fmt.Errorf("failed to create FIFO: %w", err)
	}

	if err := os.Chmod(path, 0600); err != nil {
		return "", fmt.Errorf("failed to chmod FIFO: %w", err)
	}

	return "Pipe created.", nil
}

func main() {
	directory := "Test/CWE-276_01"
	os.MkdirAll(directory, 0700)

	oldMask := syscall.Umask(0)
	defer syscall.Umask(oldMask)

	name1 := "alerts.fifo"
	path1 := directory + string(os.PathSeparator) + name1
	os.Remove(path1)

	res, err := createNotificationPipe(name1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if res != "Pipe created." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Pipe created.', got '%s'\n", res)
		os.Exit(1)
	}

	info1, err := os.Stat(path1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 stat failed: %v\n", err)
		os.Exit(1)
	}
	if info1.Mode()&os.ModeNamedPipe == 0 {
		fmt.Fprintln(os.Stderr, "Test 1 failed: not a FIFO")
		os.Exit(1)
	}
	if info1.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected perms 0600, got %o\n", info1.Mode().Perm())
		os.Exit(1)
	}

	name2 := "a_b-1.fifo"
	path2 := directory + string(os.PathSeparator) + name2
	os.Remove(path2)

	res, err = createNotificationPipe(name2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if res != "Pipe created." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Pipe created.', got '%s'\n", res)
		os.Exit(1)
	}

	info2, err := os.Stat(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 stat failed: %v\n", err)
		os.Exit(1)
	}
	if info2.Mode()&os.ModeNamedPipe == 0 {
		fmt.Fprintln(os.Stderr, "Test 2 failed: not a FIFO")
		os.Exit(1)
	}
	if info2.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected perms 0600, got %o\n", info2.Mode().Perm())
		os.Exit(1)
	}

	invalidNames := []string{"../evil.fifo", "noext", "has space.fifo", "/abs.fifo"}
	for _, invalid := range invalidNames {
		_, err := createNotificationPipe(invalid)
		if err == nil {
			fmt.Fprintf(os.Stderr, "Test invalid name failed: expected error for '%s'\n", invalid)
			os.Exit(1)
		}
	}

	// Clean up
	os.Remove(path1)
	os.Remove(path2)

	fmt.Println("All tests passed.")
}