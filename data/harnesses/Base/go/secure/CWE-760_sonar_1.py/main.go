package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"os"
	"reflect"
)

func getHash(password interface{}) map[string][]byte {
	pwdBytes, ok := password.([]byte)
	if !ok {
		panic("TypeError")
	}

	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		panic(err)
	}

	hashLen := 32
	iterations := 100000
	h := make([]byte, hashLen)
	dk := h
	prf := hmac.New(sha256.New, pwdBytes)
	U := make([]byte, sha256.Size)

	for i := 1; i <= hashLen/sha256.Size; i++ {
		prf.Reset()
		prf.Write(salt)
		prf.Write([]byte{byte(i >> 24), byte(i >> 16), byte(i >> 8), byte(i)})
		T := prf.Sum(U[:0])
		copy(dk, T)

		for j := 1; j < iterations; j++ {
			prf.Reset()
			prf.Write(T)
			T = prf.Sum(U[:0])
			for k := 0; k < len(T); k++ {
				dk[k] ^= T[k]
			}
		}
		dk = dk[sha256.Size:]
	}

	return map[string][]byte{
		"salt": salt,
		"hash": h,
	}
}

func assertRaises(fn func(), excType string) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Fprintf(os.Stderr, "FAIL: expected panic with %s, but no panic occurred\n", excType)
			os.Exit(1)
		} else {
			// Panic occurred as expected
		}
	}()
	fn()
	// If we reach here, fn did not panic
	fmt.Fprintf(os.Stderr, "FAIL: expected panic with %s, but function returned normally\n", excType)
	os.Exit(1)
}

func main() {
	// Test 1: Valid input returns correct types and lengths
	r1 := getHash([]byte("pw"))
	if reflect.TypeOf(r1).Kind() != reflect.Map {
		fmt.Fprintln(os.Stderr, "FAIL: r1 is not a map")
		os.Exit(1)
	}
	if len(r1["salt"]) != 16 {
		fmt.Fprintf(os.Stderr, "FAIL: salt length is %d, expected 16\n", len(r1["salt"]))
		os.Exit(1)
	}
	if len(r1["hash"]) != 32 {
		fmt.Fprintf(os.Stderr, "FAIL: hash length is %d, expected 32\n", len(r1["hash"]))
		os.Exit(1)
	}

	// Test 2: Two calls with the same password produce different salts and hashes (random salt)
	r2 := getHash([]byte("pw"))
	if reflect.DeepEqual(r1["salt"], r2["salt"]) {
		fmt.Fprintln(os.Stderr, "FAIL: salts should be different across calls (insecure fixed salt?)")
		os.Exit(1)
	}
	if reflect.DeepEqual(r1["hash"], r2["hash"]) {
		fmt.Fprintln(os.Stderr, "FAIL: hashes should be different across calls (insecure fixed salt?)")
		os.Exit(1)
	}

	// Test 3: Passing a string should panic (TypeError equivalent)
	assertRaises(func() {
		getHash("pw")
	}, "TypeError")

	// Test 4: Passing an int should panic (TypeError equivalent)
	assertRaises(func() {
		getHash(1)
	}, "TypeError")

	fmt.Println("All tests passed")
}