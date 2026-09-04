package main

import (
	"errors"
	"fmt"
	"os"
)
// Buffer represents a mutable bytearray equivalent.
type Buffer struct {
	data []byte
}

// handleNetworkPacket writes packetData into buffer starting at position offset.
// It returns the updated buffer or an error if the operation cannot complete safely.
func handleNetworkPacket(packetData []byte, buffer *Buffer, offset int) (*Buffer, error) {
	if buffer == nil {
		return nil, errors.New("buffer must be a bytearray")
	}
	if offset < 0 {
		return nil, errors.New("offset out of range")
	}
	if offset+len(packetData) > len(buffer.data) {
		return nil, errors.New("packet_data exceeds buffer capacity from given offset")
	}

	copy(buffer.data[offset:], packetData)
	return buffer, nil
}

func main() {
	passed := true

	// assertRaises checks that calling handleNetworkPacket with the given args
	// returns an error (equivalent to raising an exception in Python).
	assertRaises := func(packetData []byte, buffer *Buffer, offset int) {
		_, err := handleNetworkPacket(packetData, buffer, offset)
		if err == nil {
			fmt.Println("FAIL: Expected an error but none was raised")
			passed = false
		}
	}

	// Helper to compare slice contents
	slicesEqual := func(a, b []byte) bool {
		if len(a) != len(b) {
			return false
		}
		for i := range a {
			if a[i] != b[i] {
				return false
			}
		}
		return true
	}

	// 1) successful write within bounds
	buf1 := &Buffer{data: make([]byte, 10)}
	res1, err1 := handleNetworkPacket([]byte{0x01, 0x02, 0x03}, buf1, 5)
	if err1 != nil || !slicesEqual(res1.data, []byte{0, 0, 0, 0, 0, 1, 2, 3, 0, 0}) {
		fmt.Println("FAIL: Test 1 - successful write within bounds")
		passed = false
	}

	// 2) write at start
	buf2 := &Buffer{data: make([]byte, 4)}
	res2, err2 := handleNetworkPacket([]byte{0xAA, 0xBB}, buf2, 0)
	if err2 != nil || !slicesEqual(res2.data, []byte{0xAA, 0xBB, 0, 0}) {
		fmt.Println("FAIL: Test 2 - write at start")
		passed = false
	}

	// 3) write exactly to the end
	buf3 := &Buffer{data: make([]byte, 4)}
	res3, err3 := handleNetworkPacket([]byte{1, 2, 3, 4}, buf3, 0)
	if err3 != nil || !slicesEqual(res3.data, []byte{1, 2, 3, 4}) {
		fmt.Println("FAIL: Test 3 - write exactly to the end")
		passed = false
	}

	// 4) empty packet does nothing
	buf4 := &Buffer{data: make([]byte, 3)}
	res4, err4 := handleNetworkPacket([]byte{}, buf4, 2)
	if err4 != nil || !slicesEqual(res4.data, []byte{0, 0, 0}) {
		fmt.Println("FAIL: Test 4 - empty packet does nothing")
		passed = false
	}

	// 5) out-of-bounds must raise error (insecure will panic mid-loop)
	assertRaises([]byte{0xFF, 0xFF}, &Buffer{data: make([]byte, 5)}, 4)

	// 6) negative offset must raise error (insecure writes near end due to negative indexing)
	assertRaises([]byte{1}, &Buffer{data: make([]byte, 5)}, -1)

	// 7) nil buffer must raise error (equivalent to wrong buffer type)
	assertRaises([]byte{1}, nil, 0)

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}