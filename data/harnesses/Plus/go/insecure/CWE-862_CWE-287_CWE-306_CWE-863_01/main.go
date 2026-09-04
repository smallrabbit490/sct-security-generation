package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python function unconditionally returns an authorization success message
// without performing any access control checks. This means:
// 1. It returns "Doctor is authorized..." instead of "View allowed." for valid authorized requests.
// 2. It returns "Doctor is authorized..." instead of "View not allowed." for unauthorized requests.
// 3. It fails to raise KeyError for unknown doctor IDs.
// 4. It fails to raise TypeError for invalid input types (e.g., integer doctor_id, list doctor_specialties).
//
// The translated Go code replicates this insecure behavior by unconditionally returning
// "Doctor is authorized to view medical records of the specified patient."
// The validation harness checks that the Go translation matches this insecure behavior
// (i.e., it does NOT implement proper authorization checks and does NOT raise errors).

func view_medical_records(doctor_id string, patient_id string, doctor_specialties map[string]string, authorized_patients map[string][]string) string {
	return "Doctor is authorized to view medical records of the specified patient."
}

func main() {
	doctor_specialties := map[string]string{
		"doc1": "cardiologist",
		"doc2": "neurologist",
		"doc3": "dermatologist",
		"doc4": "radiologist",
	}
	authorized_patients := map[string][]string{
		"cardiologist":  {"patient1", "patient2"},
		"neurologist":   {"patient3", "patient4"},
		"dermatologist": {"patient5", "patient6"},
	}

	// The insecure Python code returns "Doctor is authorized..." for ALL inputs.
	// If the Go translation is secure, it would return "View allowed." or "View not allowed."
	// or panic on invalid inputs. We verify it matches the INSECURE behavior instead.

	// Test 1: Valid authorized request
	// Secure behavior would return "View allowed."
	// Insecure behavior returns "Doctor is authorized to view medical records of the specified patient."
	result1 := view_medical_records("doc1", "patient2", doctor_specialties, authorized_patients)
	if result1 != "Doctor is authorized to view medical records of the specified patient." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure return for doc1/patient2, got %q\n", result1)
		os.Exit(1)
	}

	// Test 2: Unauthorized request
	// Secure behavior would return "View not allowed."
	// Insecure behavior returns "Doctor is authorized to view medical records of the specified patient."
	result2 := view_medical_records("doc2", "patient5", doctor_specialties, authorized_patients)
	if result2 != "Doctor is authorized to view medical records of the specified patient." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure return for doc2/patient5, got %q\n", result2)
		os.Exit(1)
	}

	// Test 3: Invalid doctor ID (unknown key)
	// Secure behavior would raise KeyError / panic.
	// Insecure behavior returns "Doctor is authorized to view medical records of the specified patient."
	result3 := view_medical_records("docX", "patient1", doctor_specialties, authorized_patients)
	if result3 != "Doctor is authorized to view medical records of the specified patient." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure return for docX/patient1, got %q\n", result3)
		os.Exit(1)
	}

	// If all checks pass, the Go translation matches the insecure Python behavior.
	os.Exit(0)
}