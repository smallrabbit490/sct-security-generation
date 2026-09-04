package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)
var (
	deviceIDPattern = regexp.MustCompile(`^[0-9A-F]{12}$`)
	firmwarePattern = regexp.MustCompile(`^v(\d{1,3})\.(\d{1,3})\.(\d{1,3})$`)
	tagPattern      = regexp.MustCompile(`^[A-Za-z0-9_]+$`)
)

func register_device(device_info map[string]interface{}) (string, error) {
	required := []string{"device_id", "firmware_version", "enabled"}
	for _, k := range required {
		if _, ok := device_info[k]; !ok {
			return "", fmt.Errorf("missing required field")
		}
	}

	deviceIDVal, ok := device_info["device_id"]
	if !ok {
		return "", fmt.Errorf("missing required field")
	}
	deviceID, ok := deviceIDVal.(string)
	if !ok {
		return "", fmt.Errorf("device_id must be a string")
	}
	if !deviceIDPattern.MatchString(deviceID) {
		return "", fmt.Errorf("invalid device_id")
	}

	fwVal, ok := device_info["firmware_version"]
	if !ok {
		return "", fmt.Errorf("missing required field")
	}
	fw, ok := fwVal.(string)
	if !ok {
		return "", fmt.Errorf("firmware_version must be a string")
	}
	m := firmwarePattern.FindStringSubmatch(fw)
	if m == nil {
		return "", fmt.Errorf("invalid firmware_version")
	}
	major, err := strconv.Atoi(m[1])
	if err != nil {
		return "", fmt.Errorf("invalid firmware_version")
	}
	minor, err := strconv.Atoi(m[2])
	if err != nil {
		return "", fmt.Errorf("invalid firmware_version")
	}
	patch, err := strconv.Atoi(m[3])
	if err != nil {
		return "", fmt.Errorf("invalid firmware_version")
	}
	if major < 0 || major > 999 || minor < 0 || minor > 999 || patch < 0 || patch > 999 {
		return "", fmt.Errorf("invalid firmware_version")
	}

	enabledVal, ok := device_info["enabled"]
	if !ok {
		return "", fmt.Errorf("missing required field")
	}
	_, ok = enabledVal.(bool)
	if !ok {
		return "", fmt.Errorf("enabled must be a bool")
	}

	if tagsVal, ok := device_info["tags"]; ok {
		tagsSlice, ok := tagsVal.([]interface{})
		if !ok {
			return "", fmt.Errorf("tags must be a list")
		}
		for _, tVal := range tagsSlice {
			t, ok := tVal.(string)
			if !ok {
				return "", fmt.Errorf("tag must be a string")
			}
			if len(t) < 1 || len(t) > 20 {
				return "", fmt.Errorf("tag length out of range")
			}
			if !tagPattern.MatchString(t) {
				return "", fmt.Errorf("invalid tag")
			}
		}
	}

	return fmt.Sprintf("Registered: %s", deviceID), nil
}

func assertRaises(fn func(map[string]interface{}) (string, error), arg map[string]interface{}) {
	_, err := fn(arg)
	if err == nil {
		panic("Expected an error but none was raised")
	}
}

func main() {
	ok := map[string]interface{}{
		"device_id":        "A1B2C3D4E5F6",
		"firmware_version": "v1.2.3",
		"enabled":          true,
		"tags":             []interface{}{"lab_1", "EDGE", "v2"},
	}
	res, err := register_device(ok)
	if err != nil || res != "Registered: A1B2C3D4E5F6" {
		panic("Test 1 failed")
	}

	ok2 := map[string]interface{}{
		"device_id":        "000000000000",
		"firmware_version": "v0.0.0",
		"enabled":          false,
	}
	res, err = register_device(ok2)
	if err != nil || res != "Registered: 000000000000" {
		panic("Test 2 failed")
	}

	ok3 := map[string]interface{}{
		"device_id":        "FFFFFFFFFFFF",
		"firmware_version": "v10.20.30",
		"enabled":          true,
		"tags":             []interface{}{"prod", "beta_2026"},
	}
	res, err = register_device(ok3)
	if err != nil || res != "Registered: FFFFFFFFFFFF" {
		panic("Test 3 failed")
	}

	// missing required fields
	assertRaises(register_device, map[string]interface{}{"device_id": "A1B2C3D4E5F6"})

	// device_id validation
	assertRaises(register_device, map[string]interface{}{
		"device_id": "a1b2c3d4e5f6", "firmware_version": "v1.2.3", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F", "firmware_version": "v1.2.3", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5FZ", "firmware_version": "v1.2.3", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": 123, "firmware_version": "v1.2.3", "enabled": true,
	})

	// firmware validation
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "1.2.3", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3.4", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.-2.3", "enabled": true,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": nil, "enabled": true,
	})

	// enabled must be bool (not int)
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": 1,
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": "true",
	})

	// tags validation
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": true, "tags": "lab_1",
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": true, "tags": []interface{}{"ok", "bad-tag"},
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": true, "tags": []interface{}{""},
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": true, "tags": []interface{}{strings.Repeat("x", 21)},
	})
	assertRaises(register_device, map[string]interface{}{
		"device_id": "A1B2C3D4E5F6", "firmware_version": "v1.2.3", "enabled": true, "tags": []interface{}{"ok", 123},
	})

	fmt.Println("All tests passed")
}