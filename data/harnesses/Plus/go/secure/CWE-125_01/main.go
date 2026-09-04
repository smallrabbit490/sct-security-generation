package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func extractFixedRecords(blob []byte, recordSize, recordIndex, fieldOffset, fieldLength int) ([]byte, error) {
	if blob == nil {
		return nil, errors.New("blob must be bytes-like")
	}

	if recordSize <= 0 {
		return nil, errors.New("record_size must be > 0")
	}
	if recordIndex < 0 || fieldOffset < 0 || fieldLength < 0 {
		return nil, errors.New("indices must be non-negative")
	}

	if len(blob)%recordSize != 0 {
		return nil, errors.New("blob length must be a multiple of record_size")
	}

	numRecords := len(blob) / recordSize
	if recordIndex >= numRecords {
		return nil, errors.New("record_index out of range")
	}

	if fieldOffset > recordSize || fieldOffset+fieldLength > recordSize {
		return nil, errors.New("field read exceeds record boundary")
	}

	start := recordIndex*recordSize + fieldOffset
	end := start + fieldLength
	if end > len(blob) {
		return nil, errors.New("read out of bounds")
	}

	result := make([]byte, fieldLength)
	copy(result, blob[start:end])
	return result, nil
}

func main() {
	failed := false

	assertEqual := func(got, expected []byte) {
		if !reflect.DeepEqual(got, expected) {
			fmt.Printf("FAIL: expected %v, got %v\n", expected, got)
			failed = true
		}
	}

	assertError := func(err error, substr string) {
		if err == nil {
			fmt.Printf("FAIL: expected error containing %q, got nil\n", substr)
			failed = true
		}
	}

	// 3 records, each 4 bytes: [A0 A1 A2 A3][B0 B1 B2 B3][C0 C1 C2 C3]
	blob := []byte{0xA0, 0xA1, 0xA2, 0xA3, 0xB0, 0xB1, 0xB2, 0xB3, 0xC0, 0xC1, 0xC2, 0xC3}

	// valid reads
	res, err := extractFixedRecords(blob, 4, 0, 1, 2)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []byte{0xA1, 0xA2})
	}

	res, err = extractFixedRecords(blob, 4, 1, 0, 4)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []byte{0xB0, 0xB1, 0xB2, 0xB3})
	}

	res, err = extractFixedRecords(blob, 4, 2, 3, 1)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []byte{0xC3})
	}

	res, err = extractFixedRecords(blob, 4, 2, 2, 0)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []byte{})
	}

	// record_index out of range
	_, err = extractFixedRecords(blob, 4, 3, 0, 1)
	assertError(err, "record_index out of range")

	// read crosses record boundary
	_, err = extractFixedRecords(blob, 4, 0, 3, 2)
	assertError(err, "field read exceeds record boundary")

	// blob length not multiple of record_size
	badBlob := append(blob, 0x00)
	_, err = extractFixedRecords(badBlob, 4, 0, 0, 1)
	assertError(err, "blob length must be a multiple of record_size")

	// invalid types (nil blob)
	_, err = extractFixedRecords(nil, 4, 0, 0, 1)
	assertError(err, "blob must be bytes-like")

	// negative indices
	_, err = extractFixedRecords(blob, 4, 0, -1, 1)
	assertError(err, "indices must be non-negative")

	if failed {
		os.Exit(1)
	}
}