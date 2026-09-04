package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
)

// updateUserLogin is a placeholder for the external function.
// In a real scenario, this would be defined elsewhere.
var updateUserLogin func(string, map[string]interface{}) error

func storePassword(userName string, Password []byte) (interface{}, error) {
	// Check if userName is a string (already enforced by Go's type system)
	// Check if Password is a byte slice (already enforced by Go's type system)

	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return nil, err
	}

	dk := pbkdf2_hmac_sha256(Password, salt, 100000)

	record := map[string]interface{}{
		"salt": salt,
		"hash": dk,
		"algo": "pbkdf2_hmac_sha256",
	}

	// Check if updateUserLogin is defined and callable
	if updateUserLogin == nil {
		return nil, errors.New("updateUserLogin is not defined or not callable")
	}

	err := updateUserLogin(userName, record)
	return record, err
}

// pbkdf2_hmac_sha256 implements PBKDF2-HMAC-SHA256
func pbkdf2_hmac_sha256(password, salt []byte, iterations int) []byte {
	prf := hmac.New(sha256.New, password)
	hashLen := prf.Size()
	dk := make([]byte, hashLen)
	block := make([]byte, hashLen)

	for i := 1; i <= (len(dk)+hashLen-1)/hashLen; i++ {
		prf.Reset()
		prf.Write(salt)
		// Write the 4-byte big-endian representation of i
		ib := make([]byte, 4)
		binary.BigEndian.PutUint32(ib, uint32(i))
		prf.Write(ib)
		u := prf.Sum(nil)
		copy(block, u)

		for j := 1; j < iterations; j++ {
			prf.Reset()
			prf.Write(u)
			u = prf.Sum(nil)
			for k := 0; k < hashLen; k++ {
				block[k] ^= u[k]
			}
		}

		for j := 0; j < hashLen; j++ {
			if (i-1)*hashLen+j < len(dk) {
				dk[(i-1)*hashLen+j] = block[j]
			}
		}
	}

	return dk
}

func main() {
	// Mock updateUserLogin to return the record, similar to the Python test
	updateUserLogin = func(u string, rec map[string]interface{}) error {
		return nil
	}

	// Test 1: Valid call
	r1, err := storePassword("alice", []byte("pw"))
	if err != nil {
		fmt.Printf("FAIL: Valid call returned error: %v\n", err)
		os.Exit(1)
	}

	record1, ok := r1.(map[string]interface{})
	if !ok {
		fmt.Printf("FAIL: Return value is not a map\n")
		os.Exit(1)
	}

	if record1["algo"] != "pbkdf2_hmac_sha256" {
		fmt.Printf("FAIL: Algo mismatch\n")
		os.Exit(1)
	}

	salt1, ok := record1["salt"].([]byte)
	if !ok || len(salt1) != 16 {
		fmt.Printf("FAIL: Salt missing or wrong length\n")
		os.Exit(1)
	}

	hash1, ok := record1["hash"].([]byte)
	if !ok || len(hash1) != 32 {
		fmt.Printf("FAIL: Hash missing or wrong length\n")
		os.Exit(1)
	}

	// Test 2: Salt uniqueness
	r2, err := storePassword("alice", []byte("pw"))
	if err != nil {
		fmt.Printf("FAIL: Second valid call returned error: %v\n", err)
		os.Exit(1)
	}

	record2, ok := r2.(map[string]interface{})
	if !ok {
		fmt.Printf("FAIL: Second return value is not a map\n")
		os.Exit(1)
	}

	salt2, ok := record2["salt"].([]byte)
	if !ok {
		fmt.Printf("FAIL: Second salt missing\n")
		os.Exit(1)
	}

	// Compare slices manually
	saltsEqual := len(salt1) == len(salt2)
	if saltsEqual {
		for i := range salt1 {
			if salt1[i] != salt2[i] {
				saltsEqual = false
				break
			}
		}
	}

	if saltsEqual {
		fmt.Printf("FAIL: Salts are not unique\n")
		os.Exit(1)
	}

	// Test 3: Type safety (userName)
	// Go is statically typed, so we cannot pass an int for userName.
	// We verify the logic by ensuring the function signature requires a string.
	// This is a compile-time check in Go, unlike runtime in Python.

	// Test 4: Type safety (Password)
	// Go is statically typed, so we cannot pass a string for Password ([]byte).
	// This is a compile-time check in Go.

	// Test 5: updateUserLogin not defined
	updateUserLogin = nil
	_, err = storePassword("alice", []byte("pw"))
	if err == nil {
		fmt.Printf("FAIL: Expected error when updateUserLogin is nil\n")
		os.Exit(1)
	}

	fmt.Println("PASS")
}