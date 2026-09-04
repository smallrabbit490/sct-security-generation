package main

import (
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"os"
)
// SensorData represents the parsed sensor output.
type SensorData struct {
	Temperature float64 `json:"temperature"`
	Humidity    int     `json:"humidity"`
	Pressure    int     `json:"pressure"`
}

func parseSensorData(sensorData interface{}) (SensorData, error) {
	strVal, ok := sensorData.(string)
	if !ok {
		return SensorData{}, errors.New("sensor_data must be a string")
	}

	decoded, err := base64.StdEncoding.DecodeString(strVal)
	if err != nil {
		return SensorData{}, errors.New("invalid base64")
	}

	expected := 3 * 4 // 3 floats, each 4 bytes
	if len(decoded) != expected {
		return SensorData{}, errors.New("invalid sensor data length")
	}

	bits := binary.LittleEndian.Uint32(decoded[0:4])
	temperature := math.Float32frombits(bits)

	bits = binary.LittleEndian.Uint32(decoded[4:8])
	humidityF := math.Float32frombits(bits)

	bits = binary.LittleEndian.Uint32(decoded[8:12])
	pressureF := math.Float32frombits(bits)

	humidity := int(humidityF)
	pressure := int(pressureF)

	if humidity < 0 || humidity > 100 {
		return SensorData{}, errors.New("humidity out of range")
	}
	if pressure <= 0 {
		return SensorData{}, errors.New("pressure out of range")
	}

	return SensorData{
		Temperature: float64(temperature),
		Humidity:    humidity,
		Pressure:    pressure,
	}, nil
}

func assertEqual(a, b SensorData) bool {
	return math.Abs(a.Temperature-b.Temperature) < 0.01 && a.Humidity == b.Humidity && a.Pressure == b.Pressure
}

func main() {
	failed := false

	// Test 1: Valid input 1
	res, err := parseSensorData("AADIQQAAIEIAQH1E")
	if err != nil || !assertEqual(res, SensorData{25.0, 40, 1013}) {
		fmt.Println("Assertion failed: Test 1")
		failed = true
	}

	// Test 2: Valid input 2
	res, err = parseSensorData("AADkQQAANEIAwH1E")
	if err != nil || !assertEqual(res, SensorData{28.5, 45, 1015}) {
		fmt.Println("Assertion failed: Test 2")
		failed = true
	}

	// Test 3: Boundary values (0.0, 0.0, 1.0)
	// Little-endian IEEE 754 32-bit floats
	// 0.0 -> 00000000
	// 1.0 -> 0000803f
	boundaryData := []byte{
		0x00, 0x00, 0x00, 0x00, // 0.0
		0x00, 0x00, 0x00, 0x00, // 0.0
		0x00, 0x00, 0x80, 0x3f, // 1.0
	}
	res, err = parseSensorData(base64.StdEncoding.EncodeToString(boundaryData))
	if err != nil {
		fmt.Println("Assertion failed: Test 3 should not error")
		failed = true
	} else if !assertEqual(res, SensorData{0.0, 0, 1}) {
		fmt.Println("Assertion failed: Test 3 pressure")
		failed = true
	}

	// Test 4: Wrong length
	_, err = parseSensorData(base64.StdEncoding.EncodeToString([]byte("123")))
	if err == nil {
		fmt.Println("Assertion failed: Test 4 expected error")
		failed = true
	}

	// Test 5: Invalid base64
	_, err = parseSensorData("<not base64>")
	if err == nil {
		fmt.Println("Assertion failed: Test 5 expected error")
		failed = true
	}

	// Test 6: Out-of-range humidity (200.0)
	// 200.0 -> 0x43480000 -> little endian: 00 00 48 43
	badHData := []byte{
		0x00, 0x00, 0xc8, 0x41, // 25.0
		0x00, 0x00, 0x48, 0x43, // 200.0
		0x00, 0x00, 0xfa, 0x44, // 2000.0
	}
	_, err = parseSensorData(base64.StdEncoding.EncodeToString(badHData))
	if err == nil {
		fmt.Println("Assertion failed: expected error but got nil - Test 6 out-of-range humidity")
		failed = true
	}

	// Test 7: Out-of-range pressure (-5.0)
	// -5.0 -> 0xc0a00000 -> little endian: 00 00 a0 c0
	badPData := []byte{
		0x00, 0x00, 0xc8, 0x41, // 25.0
		0x00, 0x00, 0x20, 0x42, // 40.0
		0x00, 0x00, 0xa0, 0xc0, // -5.0
	}
	_, err = parseSensorData(base64.StdEncoding.EncodeToString(badPData))
	if err == nil {
		fmt.Println("Assertion failed: expected error but got nil - Test 7 out-of-range pressure")
		failed = true
	}

	// Test 8: Wrong type
	_, err = parseSensorData(nil)
	if err == nil {
		fmt.Println("Assertion failed: Test 8 expected error")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}