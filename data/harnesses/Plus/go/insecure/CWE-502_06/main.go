package main

import (
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"math"
	"os"
)
// parseSensorData is the translated insecure function.
// Insecure behavior: It does not validate humidity (0-100) or pressure (>0),
// and it panics on wrong length/invalid base64 instead of returning a ValueError.
// The secure version should raise ValueError for out-of-range humidity/pressure.
func parseSensorData(sensorData string) map[string]interface{} {
	decodedData, err := base64.StdEncoding.DecodeString(sensorData)
	if err != nil {
		panic(err)
	}

	if len(decodedData) < 12 {
		panic("not enough data")
	}

	bits := binary.LittleEndian.Uint32(decodedData[0:4])
	temperature := math.Float32frombits(bits)

	bits = binary.LittleEndian.Uint32(decodedData[4:8])
	humidity := math.Float32frombits(bits)

	bits = binary.LittleEndian.Uint32(decodedData[8:12])
	pressure := math.Float32frombits(bits)

	return map[string]interface{}{
		"temperature": temperature,
		"humidity":    int(humidity),
		"pressure":    int(pressure),
	}
}

func main() {
	passed := true

	// Inferred Python insecure outcome:
	// The insecure Python code does not validate humidity (0-100) or pressure (>0).
	// For out-of-range values, it simply returns the dictionary without raising an exception.
	// The secure version must raise a ValueError for these cases.
	// We check that the Go translation also fails to validate (i.e., returns the dict
	// without panicking), matching the insecure behavior.

	// Test 1: Out-of-range humidity (200.0)
	// Python insecure: returns {'temperature': 25.0, 'humidity': 200, 'pressure': 1013}
	// Python secure: raises ValueError
	// Go insecure: should return the dict without panicking
	badH := []byte{
		0x00, 0x00, 0xC8, 0x41, // 25.0
		0x00, 0x00, 0x48, 0x43, // 200.0
		0x00, 0x40, 0x7D, 0x44, // 1013.0
	}
	badHStr := base64.StdEncoding.EncodeToString(badH)
	func() {
		defer func() {
			if r := recover(); r != nil {
				// If it panics, it means validation was added (secure behavior).
				// The insecure translation should NOT panic here.
				fmt.Printf("FAIL: out-of-range humidity panicked (secure behavior), expected return (insecure behavior): %v\n", r)
				passed = false
			}
		}()
		res := parseSensorData(badHStr)
		h, ok := res["humidity"].(int)
		if !ok || h != 200 {
			fmt.Printf("FAIL: out-of-range humidity returned unexpected value: %v\n", res)
			passed = false
		} else {
			fmt.Println("PASS: out-of-range humidity returned dict (insecure behavior)")
		}
	}()

	// Test 2: Out-of-range pressure (-5.0)
	// Python insecure: returns {'temperature': 25.0, 'humidity': 40, 'pressure': -5}
	// Python secure: raises ValueError
	// Go insecure: should return the dict without panicking
	badP := []byte{
		0x00, 0x00, 0xC8, 0x41, // 25.0
		0x00, 0x00, 0x20, 0x42, // 40.0
		0x00, 0x00, 0xA0, 0xC0, // -5.0
	}
	badPStr := base64.StdEncoding.EncodeToString(badP)
	func() {
		defer func() {
			if r := recover(); r != nil {
				// If it panics, it means validation was added (secure behavior).
				// The insecure translation should NOT panic here.
				fmt.Printf("FAIL: out-of-range pressure panicked (secure behavior), expected return (insecure behavior): %v\n", r)
				passed = false
			}
		}()
		res := parseSensorData(badPStr)
		p, ok := res["pressure"].(int)
		if !ok || p != -5 {
			fmt.Printf("FAIL: out-of-range pressure returned unexpected value: %v\n", res)
			passed = false
		} else {
			fmt.Println("PASS: out-of-range pressure returned dict (insecure behavior)")
		}
	}()

	if !passed {
		os.Exit(1)
	}

	os.Exit(0)
}