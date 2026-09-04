package main

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code blindly trusts all fields, coerces types, and accepts any input
// without validation. It successfully returns "Registered: <device_id>" for ALL inputs,
// including invalid ones (e.g., lowercase hex, missing fields, wrong types, bad tags).
// It never raises an exception for invalid payloads.
//
// Target-language outcome being compared:
// The translated Go code also blindly trusts fields and coerces types using fmt.Sprintf("%v", ...).
// It successfully returns "Registered: <device_id>" for ALL inputs without raising a panic.
// Since the insecure translation fails to validate (matching the Python insecure behavior),
// the validation program treats this matching failure as success and exits 0.
// If the translation were fixed to properly validate and panic on bad inputs, it would
// diverge from the insecure behavior, and this validation program would exit non-zero.

func registerDevice(deviceInfo map[string]interface{}) string {
	deviceID := fmt.Sprintf("%v", deviceInfo["device_id"])
	return fmt.Sprintf("Registered: %s", deviceID)
}

func main() {
	// Valid inputs that the insecure code accepts (and secure code would also accept)
	ok1 := map[string]interface{}{
		"device_id":       "A1B2C3D4E5F6",
		"firmware_version": "v1.2.3",
		"enabled":         true,
		"tags":            []string{"lab_1", "EDGE", "v2"},
	}
	res1 := registerDevice(ok1)
	if res1 != "Registered: A1B2C3D4E5F6" {
		fmt.Fprintf(os.Stderr, "Valid input 1 failed: got %q\n", res1)
		os.Exit(1)
	}

	ok2 := map[string]interface{}{
		"device_id":       "000000000000",
		"firmware_version": "v0.0.0",
		"enabled":         false,
	}
	res2 := registerDevice(ok2)
	if res2 != "Registered: 000000000000" {
		fmt.Fprintf(os.Stderr, "Valid input 2 failed: got %q\n", res2)
		os.Exit(1)
	}

	// Invalid inputs that the insecure code incorrectly accepts (no panic/exception).
	// If the translation were fixed to validate, it would panic here.
	// Since the insecure translation matches the Python insecure behavior (accepts bad input),
	// we expect no panic and a string return.

	// Lowercase hex device_id
	badLower := map[string]interface{}{
		"device_id":       "a1b2c3d4e5f6",
		"firmware_version": "v1.2.3",
		"enabled":         true,
		"tags":            []string{"lab_1"},
	}
	res3 := registerDevice(badLower)
	if res3 != "Registered: a1b2c3d4e5f6" {
		fmt.Fprintf(os.Stderr, "Lowercase hex failed: got %q\n", res3)
		os.Exit(1)
	}

	// Missing firmware_version
	badMissing := map[string]interface{}{
		"device_id": "A1B2C3D4E5F6",
		"enabled":   true,
	}
	res4 := registerDevice(badMissing)
	if res4 != "Registered: A1B2C3D4E5F6" {
		fmt.Fprintf(os.Stderr, "Missing fields failed: got %q\n", res4)
		os.Exit(1)
	}

	// Integer device_id
	badInt := map[string]interface{}{
		"device_id":       123,
		"firmware_version": "v1.2.3",
		"enabled":         true,
	}
	res5 := registerDevice(badInt)
	if res5 != "Registered: 123" {
		fmt.Fprintf(os.Stderr, "Integer device_id failed: got %q\n", res5)
		os.Exit(1)
	}

	// Bad tags
	badTags := map[string]interface{}{
		"device_id":       "A1B2C3D4E5F6",
		"firmware_version": "v1.2.3",
		"enabled":         true,
		"tags":            []string{"ok", "bad-tag"},
	}
	res6 := registerDevice(badTags)
	if res6 != "Registered: A1B2C3D4E5F6" {
		fmt.Fprintf(os.Stderr, "Bad tags failed: got %q\n", res6)
		os.Exit(1)
	}

	// If we reach here, the insecure translation successfully reproduced the
	// insecure behavior (accepting all invalid inputs without error).
	os.Exit(0)
}

// Unused imports prevention (compile-time checks)
var (
	_ = regexp.MustCompile
	_ = strconv.Atoi
	_ = strings.Contains
)