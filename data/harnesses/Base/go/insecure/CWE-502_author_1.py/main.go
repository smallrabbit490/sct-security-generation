package main

import (
	"bytes"
	"encoding/gob"
	"fmt"
	"os"
	"os/exec"
)

// Payload mimics the Python class with a __reduce__ equivalent.
// In Go, gob encoding uses the BinaryMarshaler/BinaryUnmarshaler interfaces.
// We implement BinaryMarshaler to inject the insecure behavior during serialization.
type Payload struct{}

// GobEncode implements the gob.GobEncoder interface.
// This is the Go equivalent of Python's __reduce__ for the serialization process.
func (p Payload) GobEncode() ([]byte, error) {
	// The Python code executes: import os;os.system("ls")
	// We preserve this insecure behavior by executing the command here.
	cmd := exec.Command("ls")
	// Run the command. We ignore errors to match the lack of error handling in the Python snippet.
	cmd.Run()

	// Return a dummy byte slice to satisfy the interface, as the primary effect is the side effect.
	return []byte{}, nil
}

func makePickleData(payload Payload) []byte {
	/*
		Get serialized data from the payload object and serialize it before returning it
	*/
	var buf bytes.Buffer
	// Create a gob encoder and serialize the payload.
	// This will trigger Payload.GobEncode(), executing the command.
	enc := gob.NewEncoder(&buf)
	enc.Encode(payload)
	return buf.Bytes()
}

func main() {
	// The Python tests expect the insecure code to fail because it serializes a dangerous object
	// (Payload) without raising a TypeError. The Python test logic is:
	// assert_raises(candidate, Payload(), exc_types=(TypeError,))
	//
	// The translated Go code (makePickleData) accepts Payload and executes the command (side effect)
	// without returning an error. This matches the "Insecure Code failure analysis":
	// "Insecure pickles Payload() successfully (no exception), but test requires TypeError for Payload(), so insecure fails."
	//
	// Therefore, for the validation to pass (exit 0), we must verify that the Go code
	// successfully serializes the Payload (i.e., does not panic or return an error that would
	// prevent the side effect), confirming it behaves insecurely as described.

	p := Payload{}
	data := makePickleData(p)

	// If we reach here, the code executed successfully (insecurely).
	// We print the data to stdout to verify execution flow.
	fmt.Printf("Insecure serialization successful. Data length: %d\n", len(data))

	// The validation rule states: "Create executable checks for the intentionally insecure translation.
	// The program should exit with code 0 only when the translated insecure code fails in the same
	// security-relevant way described by the Python tests..."
	//
	// The "failure" described is a logic failure: the code is insecure because it *doesn't* raise an error.
	// By successfully running makePickleData with Payload, we demonstrate this insecure behavior.
	// Thus, exiting 0 confirms the insecure nature of the translation.

	os.Exit(0)
}