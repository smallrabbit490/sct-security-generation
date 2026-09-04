package main

import (
	"fmt"
	"os"
	"syscall"
)
// createNotificationPipe is the translated insecure Go function.
// Insecure behavior: It creates a FIFO with permissive 0666 permissions and
// then explicitly widens them with os.Chmod(path, 0666), making the pipe
// readable and writable by all users (CWE-276).
func createNotificationPipe(pipeName string) (string, error) {
	directory := "Test/CWE-WEAK_01"
	err := os.MkdirAll(directory, 0777)
	if err != nil {
		return "", err
	}
	path := directory + "/" + pipeName

	if _, err := os.Stat(path); err == nil {
		err = os.Remove(path)
		if err != nil {
			return "", err
		}
	}

	err = syscall.Mkfifo(path, 0666)
	if err != nil {
		return "", err
	}

	err = os.Chmod(path, 0666)
	if err != nil {
		return "", err
	}

	return "Pipe created.", nil
}

func main() {
	// Inferred Python insecure outcome:
	// The original Python code creates a FIFO with 0o666 permissions and then
	// explicitly calls os.chmod(path, 0o666). The secure test expects 0o600
	// (owner-only) and will fail because the insecure code produces 0o666.
	//
	// Target-language outcome being compared:
	// We check if the Go translation also produces the insecure 0666 permissions
	// (or wider) instead of the secure 0600. If the translation is insecure
	// (permissions >= 0666), the validation succeeds (exit 0). If the translation
	// is secure (permissions == 0600), the validation fails (exit non-zero).

	directory := "Test/CWE-WEAK_01"
	err := os.MkdirAll(directory, 0777)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}

	// Set umask to 0 so that Mkfifo creates exactly the requested permissions
	// without masking out any bits.
	oldUmask := syscall.Umask(0)
	defer syscall.Umask(oldUmask)

	pipeName := "alerts.fifo"
	path := directory + "/" + pipeName

	// Clean up any pre-existing file
	if _, err := os.Stat(path); err == nil {
		os.Remove(path)
	}

	// Call the translated insecure function
	result, err := createNotificationPipe(pipeName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Function returned unexpected error: %v\n", err)
		os.Exit(2)
	}

	if result != "Pipe created." {
		fmt.Fprintf(os.Stderr, "Unexpected return value: %s\n", result)
		os.Exit(2)
	}

	// Check the actual permissions on the created FIFO
	info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to stat pipe: %v\n", err)
		os.Exit(2)
	}

	perms := info.Mode().Perm()

	// The secure test expects 0600. The insecure code produces 0666.
	// If the permissions are 0666 (or wider), the vulnerability is present,
	// matching the insecure Python outcome.
	if perms == 0666 {
		fmt.Println("Insecure behavior confirmed: permissions are 0666")
		os.Exit(0)
	}

	// If permissions are restricted (e.g., 0600), the vulnerability was fixed.
	fmt.Fprintf(os.Stderr, "Secure behavior detected: permissions are %04o, expected insecure 0666\n", perms)
	os.Exit(1)
}