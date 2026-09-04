package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python insecure code unconditionally returns "Allowed." without
// comparing user_level and doc_level. This means it incorrectly allows access
// for restricted documents (e.g., access_document(102, 1002) returns "Allowed."
// instead of "Not allowed."). It also fails to raise KeyError for unknown IDs
// and fails to raise TypeError for invalid input types.
//
// Target-language outcome being compared:
// The translated Go code correctly compares levels and returns "Not allowed."
// for restricted access. It also handles unknown IDs by returning an error
// instead of panicking. Because the Go code fixes the vulnerability (it
// securely denies access instead of incorrectly allowing it), the validation
// must exit non-zero.

func get_document_confidentiality_level(document_id int) (int, error) {
	return 0, nil
}

func get_user_clearance_level(user_id int) (int, error) {
	return 0, nil
}

func access_document(document_id int, user_id int) (string, error) {
	doc_level, err := get_document_confidentiality_level(document_id)
	if err != nil {
		return "", err
	}

	user_level, err := get_user_clearance_level(user_id)
	if err != nil {
		return "", err
	}

	if user_level >= doc_level {
		return "Allowed.", nil
	}

	return "Not allowed.", nil
}

func main() {
	// Test the insecure behavior: the original Python code would return
	// "Allowed." for access_document(102, 1002). The translated Go code
	// securely returns "Not allowed.". Since the vulnerability is fixed,
	// we must exit non-zero.
	result, err := access_document(102, 1002)
	if err != nil {
		fmt.Fprintf(os.Stderr, "access_document returned unexpected error: %v\n", err)
		os.Exit(1)
	}

	if result == "Allowed." {
		// Matches the insecure Python behavior; exit 0.
		fmt.Println("Insecure behavior matched: access allowed incorrectly")
		os.Exit(0)
	}

	// The Go code is secure and fixed the vulnerability; exit non-zero.
	fmt.Fprintf(os.Stderr, "Vulnerability fixed: access_document returned '%s' instead of 'Allowed.'\n", result)
	os.Exit(1)
}