package main

import (
	"fmt"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code performs an out-of-bounds write without bounds checking.
// For out-of-bounds indices (e.g., offset + len(packet_data) > len(buffer)), it raises an IndexError mid-loop.
// For negative offsets, Python's negative indexing causes it to write near the end of the buffer, 
// and then raises an IndexError if it wraps around or exceeds bounds.
// For incorrect types (e.g., passing a string or immutable bytes), it raises a TypeError.
// The insecure behavior is that it panics/raises on out-of-bounds or type errors, rather than safely handling them.

// Translated Go code:
func handleNetworkPacket(packetData []byte, buffer []byte, offset int) []byte {
	for i, b := range packetData {
		buffer[offset+i] = b
	}
	return buffer
}

func main() {
	exitCode := 0

	// Helper to check if a function call panics
	assertPanics := func(f func(), testName string) {
		defer func() {
			if r := recover(); r != nil {
				// Panic occurred, matching the insecure Python behavior (raising an exception)
			} else {
				fmt.Fprintf(os.Stderr, "FAIL: %s - expected panic but none was raised\n", testName)
				exitCode = 1
			}
		}()
		f()
	}

	// 1) successful write within bounds
	buf1 := make([]byte, 10)
	expected1 := []byte{0, 0, 0, 0, 0, 1, 2, 3, 0, 0}
	result1 := handleNetworkPacket([]byte{0x01, 0x02, 0x03}, buf1, 5)
	if !reflect.DeepEqual(result1, expected1) {
		fmt.Fprintf(os.Stderr, "FAIL: Test 1 - expected %v, got %v\n", expected1, result1)
		exitCode = 1
	}

	// 2) write at start
	buf2 := make([]byte, 4)
	expected2 := []byte{0xAA, 0xBB, 0, 0}
	result2 := handleNetworkPacket([]byte{0xAA, 0xBB}, buf2, 0)
	if !reflect.DeepEqual(result2, expected2) {
		fmt.Fprintf(os.Stderr, "FAIL: Test 2 - expected %v, got %v\n", expected2, result2)
		exitCode = 1
	}

	// 3) write exactly to the end
	buf3 := make([]byte, 4)
	expected3 := []byte{1, 2, 3, 4}
	result3 := handleNetworkPacket([]byte{1, 2, 3, 4}, buf3, 0)
	if !reflect.DeepEqual(result3, expected3) {
		fmt.Fprintf(os.Stderr, "FAIL: Test 3 - expected %v, got %v\n", expected3, result3)
		exitCode = 1
	}

	// 4) empty packet does nothing
	buf4 := make([]byte, 3)
	expected4 := []byte{0, 0, 0}
	result4 := handleNetworkPacket([]byte{}, buf4, 2)
	if !reflect.DeepEqual(result4, expected4) {
		fmt.Fprintf(os.Stderr, "FAIL: Test 4 - expected %v, got %v\n", expected4, result4)
		exitCode = 1
	}

	// 5) out-of-bounds must panic (insecure will raise IndexError mid-loop)
	assertPanics(func() {
		buf5 := make([]byte, 5)
		handleNetworkPacket([]byte{0xFF, 0xFF}, buf5, 4)
	}, "Test 5 (out-of-bounds)")

	// 6) negative offset must panic (insecure writes near end due to negative indexing, then raises IndexError)
	assertPanics(func() {
		buf6 := make([]byte, 5)
		handleNetworkPacket([]byte{1}, buf6, -1)
	}, "Test 6 (negative offset)")

	// 7) wrong buffer type must panic (Python raises TypeError; Go will fail at compile time if type is wrong, 
	// but if forced via interface{}, it panics at runtime. We check that it doesn't silently pass).
	assertPanics(func() {
		// In Go, passing a string to a []byte parameter is a compile-time error.
		// To simulate the runtime TypeError check from Python, we use reflection to invoke 
		// the function with the wrong type, which will result in a runtime panic.
		val := reflect.ValueOf(handleNetworkPacket)
		args := []reflect.Value{
			reflect.ValueOf([]byte{1}),
			reflect.ValueOf("not-bytes"), // wrong type for buffer
			reflect.ValueOf(0),
		}
		val.Call(args)
	}, "Test 7 (wrong buffer type)")

	// 8) wrong packet type must panic (Python raises TypeError)
	assertPanics(func() {
		val := reflect.ValueOf(handleNetworkPacket)
		args := []reflect.Value{
			reflect.ValueOf("not-bytes"), // wrong type for packetData
			reflect.ValueOf(make([]byte, 2)),
			reflect.ValueOf(0),
		}
		val.Call(args)
	}, "Test 8 (wrong packet type)")

	os.Exit(exitCode)
}