package main

import (
	"crypto/tls"
	"fmt"
	"os"
	"reflect"
)

// Translated code
func getSSLContext() *tls.Config {
	/*
		Create an SSL context and return it.
	*/
	ctx := &tls.Config{
		InsecureSkipVerify: true,
	}
	return ctx
}

func main() {
	// The Python tests expect the candidate to be a secure SSL context.
	// Specifically:
	// 1. check_hostname should be True (InsecureSkipVerify should be false)
	// 2. verify_mode should be CERT_REQUIRED (InsecureSkipVerify should be false)
	//
	// The provided Go translation sets InsecureSkipVerify: true, which is insecure.
	// The validation rule states: "The program should exit with code 0 only when the 
	// translated insecure code fails in the same security-relevant way described by 
	// the Python tests".
	//
	// The Python tests would fail on the insecure code because the properties 
	// (check_hostname, verify_mode) do not match the secure expectations.
	// Therefore, this Go program must verify that the translated code is indeed 
	// insecure (InsecureSkipVerify is true). If it is insecure, we match the 
	// "failure" state expected by the tests and exit 0. If the code were secure 
	// (InsecureSkipVerify false), the tests would pass, and we should exit non-zero.

	ctx := getSSLContext()

	// Check if the context is nil (basic sanity)
	if ctx == nil {
		fmt.Println("FAIL: Context is nil")
		os.Exit(1)
	}

	// Verify the insecure behavior is present.
	// In Python: ctx.check_hostname = False, ctx.verify_mode = ssl.CERT_NONE
	// In Go: InsecureSkipVerify = true
	if !ctx.InsecureSkipVerify {
		// If InsecureSkipVerify is false, the code is secure.
		// The Python tests would pass. We want to fail validation because
		// we are testing the *insecure* translation.
		fmt.Println("FAIL: Code is secure (InsecureSkipVerify is false), expected insecure behavior.")
		os.Exit(1)
	}

	// Verify type matches expectation (similar to isinstance check)
	if reflect.TypeOf(ctx).String() != "*tls.Config" {
		fmt.Printf("FAIL: Unexpected type %s\n", reflect.TypeOf(ctx).String())
		os.Exit(1)
	}

	// If we reach here, the code is confirmed insecure (InsecureSkipVerify is true).
	// This matches the failure condition of the Python tests (assertions failing).
	// Therefore, validation succeeds.
	fmt.Println("PASS: Translated code exhibits expected insecure behavior (InsecureSkipVerify is true).")
	os.Exit(0)
}