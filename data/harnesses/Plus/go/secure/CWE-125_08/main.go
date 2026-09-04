package main

import (
	"fmt"
	"os"
	"strings"
)
func analyzePacket(packets []int, packetIndex int, offset int, bytesToExtract int) (string, error) {
	for _, b := range packets {
		if b < 0 || b > 255 {
			return "", fmt.Errorf("packet bytes must be in [0, 255]")
		}
	}
	if packetIndex < 0 || offset < 0 || bytesToExtract < 0 {
		return "", fmt.Errorf("indices must be non-negative")
	}

	pos := 0
	current := 0
	for {
		if pos+2 > len(packets) {
			return "", fmt.Errorf("packet_index out of range")
		}
		size := packets[pos+1]
		if size < 0 || size > 255 {
			return "", fmt.Errorf("invalid payload size")
		}
		payloadStart := pos + 2
		payloadEnd := payloadStart + size
		if payloadEnd > len(packets) {
			return "", fmt.Errorf("truncated packet")
		}
		if current == packetIndex {
			if offset > size || offset+bytesToExtract > size {
				return "", fmt.Errorf("extraction out of range")
			}
			start := payloadStart + offset
			data := packets[start : start+bytesToExtract]
			strs := make([]string, len(data))
			for i, v := range data {
				strs[i] = fmt.Sprintf("%d", v)
			}
			return "Extracted Data: [" + strings.Join(strs, ", ") + "]", nil
		}
		pos = payloadEnd
		current++
	}
}

func main() {
	failed := false

	assertEqual := func(got, want string) {
		if got != want {
			fmt.Fprintf(os.Stderr, "FAIL: got %q, want %q\n", got, want)
			failed = true
		}
	}

	assertError := func(err error) {
		if err == nil {
			fmt.Fprintln(os.Stderr, "FAIL: expected an error but none was raised")
			failed = true
		}
	}

	packets := []int{0x01, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x02, 0x03, 0x11, 0x22, 0x33}

	// valid extraction first packet
	res, err := analyzePacket(packets, 0, 1, 3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "Extracted Data: [187, 204, 221]")
	}

	// valid extraction second packet
	res, err = analyzePacket(packets, 1, 0, 3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "Extracted Data: [17, 34, 51]")
	}

	// single byte extraction
	res, err = analyzePacket(packets, 0, 0, 1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "Extracted Data: [170]")
	}

	// empty extraction
	res, err = analyzePacket(packets, 1, 2, 0)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "Extracted Data: []")
	}

	// out-of-range extraction must raise
	_, err = analyzePacket(packets, 1, 0, 4)
	assertError(err)

	// packet_index out of range must raise
	_, err = analyzePacket(packets, 2, 0, 1)
	assertError(err)

	// negative inputs must raise
	_, err = analyzePacket(packets, 0, -1, 1)
	assertError(err)

	// malformed packets (truncated payload) must raise
	badPackets := []int{0x01, 0x05, 1, 2, 3}
	_, err = analyzePacket(badPackets, 0, 0, 1)
	assertError(err)

	if failed {
		os.Exit(1)
	}
}