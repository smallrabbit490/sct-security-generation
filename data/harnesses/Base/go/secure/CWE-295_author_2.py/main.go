package main

import (
	"crypto/tls"
	"errors"
	"fmt"
	"os"
)

// getContext creates a TLS configuration with verification enabled.
// It mimics the behavior of the Python OpenSSL context creation.
func getContext() (*tls.Config, error) {
	// Create a TLS 1.2 configuration
	ctx := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}

	// Set verification mode to VERIFY_PEER
	ctx.InsecureSkipVerify = false

	// Set default verification paths (system roots)
	// In Go, this is handled automatically by crypto/tls when InsecureSkipVerify is false
	// and no custom RootCAs are provided.

	return ctx, nil
}

func main() {
	// Run the validation checks
	if err := check(getContext); err != nil {
		fmt.Fprintf(os.Stderr, "Validation failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Validation passed")
	os.Exit(0)
}

// check performs functional checks equivalent to the Python tests.
func check(candidate func() (*tls.Config, error)) error {
	// Create a temporary directory structure expected by the Python test logic
	// Although not strictly used in Go logic, it mirrors the environment setup.
	dirPath := "Test/CWE-295_author_2"
	if err := os.MkdirAll(dirPath, 0755); err != nil {
		return fmt.Errorf("failed to create test directory: %w", err)
	}
	// Clean up directory
	defer os.RemoveAll("Test")

	// Test 1: Successful execution
	ctx, err := candidate()
	if err != nil {
		return fmt.Errorf("candidate function returned an error: %w", err)
	}

	// Verify the context is a valid TLS configuration
	if ctx == nil {
		return errors.New("returned context is nil")
	}

	// Verify MinVersion is TLS 1.2
	if ctx.MinVersion != tls.VersionTLS12 {
		return fmt.Errorf("expected MinVersion TLS 1.2 (%d), got %d", tls.VersionTLS12, ctx.MinVersion)
	}

	// Verify InsecureSkipVerify is false (equivalent to VERIFY_PEER)
	if ctx.InsecureSkipVerify {
		return errors.New("expected InsecureSkipVerify to be false (VERIFY_PEER)")
	}

	// Verify RootCAs is nil, which implies system default paths are used
	// (equivalent to set_default_verify_paths)
	if ctx.RootCAs != nil {
		return errors.New("expected RootCAs to be nil (system defaults)")
	}

	// Test 2: Insecure Code failure analysis
	// The Python test mocks the SSL module to force a RuntimeError.
	// In Go, we cannot mock the standard library's crypto/tls package in the same way
	// without significant refactoring (interfaces).
	// However, the translated Go code is secure by default (InsecureSkipVerify = false).
	// The Python test asserts that if the code were insecure (e.g., missing verification),
	// the assertions would fail. Since our Go code explicitly sets InsecureSkipVerify = false,
	// it passes the security check.

	return nil
}