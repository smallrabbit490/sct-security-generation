package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
func archiveDirectory(directory string, destTarPath string) (string, error) {
	// Insecure: string concatenation with user-controlled strings enables command injection
	cmd := fmt.Sprintf("tar -cf %s -C %s .", destTarPath, directory)
	out, err := exec.Command("sh", "-c", cmd).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("command failed: %v: %s", err, string(out))
	}
	return fmt.Sprintf("Archived to %s", destTarPath), nil
}

func main() {
	base := filepath.Join("Test", "CWE-78_10")
	os.RemoveAll(base)
	os.MkdirAll(base, 0755)

	d := filepath.Join(base, "dirA")
	os.MkdirAll(d, 0755)
	os.WriteFile(filepath.Join(d, "a.txt"), []byte("A"), 0644)
	os.WriteFile(filepath.Join(d, "b.txt"), []byte("B"), 0644)

	outTar := filepath.Join(base, "out.tar")

	// Test 1: Normal archiving should succeed
	msg, err := archiveDirectory(d, outTar)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: normal archive returned error: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasSuffix(msg, "out.tar") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected message ending with out.tar, got %s\n", msg)
		os.Exit(1)
	}

	// Test 2: Injection-like string should NOT be executed as a command.
	// Inferred Python insecure outcome: The insecure Python code uses shell=True with
	// string concatenation, allowing command injection. The injection string
	// "dirA; echo hacked" would be interpreted by the shell as two commands.
	// The second command ("echo hacked") would execute successfully, and the overall
	// shell command would likely succeed (exit 0) because the last command succeeded,
	// returning "Archived to ..." without raising an exception.
	//
	// Target-language outcome being compared: The Go translation also uses shell
	// execution via `exec.Command("sh", "-c", cmd)`, making it equally vulnerable.
	// If the injection string is passed, the shell will execute the injected command
	// and return without an error, matching the insecure Python behavior.
	// If the Go code were secure (e.g., using exec.Command arguments without shell),
	// it would treat the entire string as a directory path, fail to find it, and return an error.
	// We validate that the insecure translation fails to block the injection (returns no error).
	injectionDir := d + "; echo hacked"
	_, injErr := archiveDirectory(injectionDir, outTar)
	if injErr != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: injection string was not executed (secure behavior), got error: %v\n", injErr)
		os.Exit(1)
	}

	fmt.Println("All validation checks passed (insecure behavior confirmed)")
}