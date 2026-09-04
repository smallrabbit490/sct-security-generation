package main

import (
	"crypto/tls"
	"fmt"
	"os"
)

// getContext is the translated function.
func getContext() *tls.Config {
	/*
	   Create an OpenSSL context and return it.
	*/
	ctx := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}
	return ctx
}

func main() {
	// The Python test mocks the OpenSSL library to verify that the context
	// is configured with specific security settings (VERIFY_PEER and set_default_verify_paths).
	// The Python test asserts:
	// 1. ctx.verify == 1 (SSL.VERIFY_PEER)
	// 2. ctx.paths is True (set_default_verify_paths was called)
	//
	// The translated Go code returns a standard tls.Config.
	// In Go's tls.Config, the equivalent of VERIFY_PEER is InsecureSkipVerify = false (default).
	// However, Go does not have a direct boolean flag equivalent to "set_default_verify_paths was called".
	// The Python test logic is:
	// - If the code is secure (calls set_verify/set_default_verify_paths), assertions pass.
	// - If the code is insecure (does not call them), assertions fail.
	//
	// The "Insecure Code failure analysis" states:
	// "Insecure does not enable verification/default verify paths; it will not set ctx.verify/paths and thus fails the assertions."
	//
	// Therefore, to validate the *insecure* translation, we must verify that the Go code
	// does NOT implement the specific security checks that the Python mock was looking for.
	// Since Go's tls.Config does not have a "VerifyPaths" boolean, we cannot check for it directly.
	// However, we can check the state of InsecureSkipVerify.
	//
	// If the translation were "secure" (mimicking the Python test's expectations), it might explicitly
	// set InsecureSkipVerify = false or configure a custom verification callback.
	// The provided translation is minimal: `MinVersion: tls.VersionTLS12`.
	// It relies on Go's defaults.
	//
	// To pass the validation rule ("Exit with code 0 only for matching insecure behavior"),
	// we check that the context is indeed the minimal, insecure configuration described.
	// Specifically, we check that it does NOT contain explicit security overrides that would
	// satisfy the Python test's "assert ctx.verify == 1" logic if we were mapping 1:1.
	//
	// More concretely, the Python test expects the code to fail if it doesn't set verify/paths.
	// The validator should succeed if the code *is* the insecure version.
	// The insecure version is defined by the lack of those calls.
	// In Go, the lack of those calls corresponds to the default Config state.
	//
	// We verify that the Config returned matches the insecure translation exactly.
	// If the code were changed to be secure (e.g., adding InsecureSkipVerify: false explicitly
	// or setting up RootCAs), it might be considered "fixed", but the Python test logic
	// implies that the "insecure" version simply lacks the setup.
	//
	// The most robust check for the "insecure" behavior in this context is to ensure
	// that the Config is the minimal one provided in the translation.
	// If the Config were nil or panic'd, that would be a failure.
	// If the Config had explicit verification settings, it might be a "fix".
	// But given the translation, we just check that it returns the specific insecure struct.

	ctx := getContext()

	// Check 1: Context is not nil.
	if ctx == nil {
		fmt.Fprintln(os.Stderr, "FAIL: Context is nil")
		os.Exit(1)
	}

	// Check 2: MinVersion is set to TLS 1.2 (as per the translation).
	if ctx.MinVersion != tls.VersionTLS12 {
		fmt.Fprintf(os.Stderr, "FAIL: MinVersion is %d, expected %d\n", ctx.MinVersion, tls.VersionTLS12)
		os.Exit(1)
	}

	// Check 3: InsecureSkipVerify must be false (default).
	// If it were true, it would be explicitly insecure in a different way, but the Python
	// test is about the *absence* of enabling verification.
	// The default false is the "insecure" state relative to the Python test's requirement
	// to explicitly set it.
	if ctx.InsecureSkipVerify {
		fmt.Fprintln(os.Stderr, "FAIL: InsecureSkipVerify is true")
		os.Exit(1)
	}

	// Check 4: RootCAs should be nil (default system roots are used implicitly, but not explicitly set).
	// The Python test checks `set_default_verify_paths`. In Go, this is implicit.
	// The "insecure" code doesn't do anything. The "secure" code (in Python) does.
	// Since we are validating the *insecure* translation, we expect the default state.
	// If RootCAs were explicitly set to a non-nil pool, that would be a change in behavior.
	if ctx.RootCAs != nil {
		fmt.Fprintln(os.Stderr, "FAIL: RootCAs is not nil (explicitly set)")
		os.Exit(1)
	}

	// If all checks pass, the code behaves as the "insecure" translation is expected to:
	// It returns a context with MinVersion set, but relies entirely on defaults for verification,
	// failing the Python test's requirement for explicit setup.
	os.Exit(0)
}