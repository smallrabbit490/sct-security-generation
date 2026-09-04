package main

import (
	"fmt"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code uses an incorrect formula for calculating the start index
// of a packet's payload: `packet_index * (2 + packets[1 + packet_index * 3]) + offset`.
// This formula fails to correctly skip previous packets' payloads, causing it to read
// from the wrong memory location (an out-of-bounds read / CWE-125).
// For `packets = [0x01, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x02, 0x03, 0x11, 0x22, 0x33]`,
// `packet_index = 0, offset = 1, bytes_to_extract = 3`, the insecure Python code
// incorrectly calculates `startIndex = 1` and returns "Extracted Data: [4, 170, 187]".
// The secure implementation would correctly calculate `startIndex = 3` and return
// "Extracted Data: [187, 204, 221]". The validation must ensure the Go translation
// exhibits the same insecure behavior (returning the wrong, out-of-bounds data).

func analyzePacket(packets []int, packetIndex int, offset int, bytesToExtract int) string {
	// Assuming packet header (type + size) is 2 bytes.
	startIndex := packetIndex*(2+packets[1+packetIndex*3]) + offset
	if startIndex < 0 || startIndex+bytesToExtract > len(packets) {
		panic("runtime error: index out of range")
	}
	extractedData := packets[startIndex : startIndex+bytesToExtract]
	strs := make([]string, len(extractedData))
	for i, v := range extractedData {
		strs[i] = fmt.Sprintf("%d", v)
	}
	return fmt.Sprintf("Extracted Data: [%s]", strings.Join(strs, ", "))
}

func main() {
	packets := []int{0x01, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x02, 0x03, 0x11, 0x22, 0x33}

	// Target-language outcome being compared:
	// We check if the Go translation produces the same insecure, incorrect result
	// as the Python code. If it returns the secure correct value, the vulnerability
	// was fixed, and we must exit non-zero.
	insecureResult := "Extracted Data: [4, 170, 187]"
	actualResult := analyzePacket(packets, 0, 1, 3)

	if actualResult != insecureResult {
		fmt.Printf("Validation failed: expected insecure result %q but got %q\n", insecureResult, actualResult)
		fmt.Println("The vulnerability appears to be fixed.")
		// Exit non-zero if the insecure behavior is not present
		panic("validation failure")
	}

	fmt.Println("Validation passed: insecure behavior matched.")
}