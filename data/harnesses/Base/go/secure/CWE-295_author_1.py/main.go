package main

import (
	"crypto/tls"
	"os"
)

func getSSLContext() *tls.Config {
	ctx := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}

	// Ensure certificate verification is enabled
	if ctx.InsecureSkipVerify {
		panic("InsecureSkipVerify is true")
	}

	ctx.InsecureSkipVerify = false

	if ctx.InsecureSkipVerify {
		panic("InsecureSkipVerify is still true")
	}

	return ctx
}

func main() {
	// Test 1: Check that getSSLContext returns a valid *tls.Config
	ctx := getSSLContext()
	if ctx == nil {
		os.Exit(1)
	}

	// Test 2: Ensure InsecureSkipVerify is false (equivalent to check_hostname=True and verify_mode=CERT_REQUIRED)
	if ctx.InsecureSkipVerify {
		os.Exit(1)
	}

	// Test 3: Ensure MinVersion is at least TLS 1.2
	if ctx.MinVersion < tls.VersionTLS12 {
		os.Exit(1)
	}

	// Test 4: Check that calling getSSLContext with arguments raises a compile-time error.
	// In Go, passing arguments to a function that takes none results in a compilation failure.
	// To simulate the Python test's `assert_raises(candidate, 1, exc_types=(TypeError,))`,
	// we verify the function signature accepts no arguments by attempting to call it without arguments.
	// If the function incorrectly accepted arguments, it would need a different signature.
	// Since Go is statically typed, this is inherently enforced at compile time.
	// We call it again to ensure it remains stable and returns a valid context.
	ctx2 := getSSLContext()
	if ctx2 == nil {
		os.Exit(1)
	}
	if ctx2.InsecureSkipVerify {
		os.Exit(1)
	}

	// Test 5: Insecure code failure analysis
	// Insecure code would set InsecureSkipVerify to true, which would fail the above checks.
	// The getSSLContext function explicitly checks and panics if InsecureSkipVerify is true,
	// ensuring secure defaults are maintained.

	os.Exit(0)
}