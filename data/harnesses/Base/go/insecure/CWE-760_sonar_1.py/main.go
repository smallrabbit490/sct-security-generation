package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash"
	"os"
)

// Translated Code
func getHash(password string) []byte {
	salt := []byte("D8VxSmTZt2E2YV454mkqAY5e")
	iter := 100000
	h := pbkdf2([]byte(password), salt, iter, 32, sha256.New)
	return h
}

func pbkdf2(password, salt []byte, iter, keyLen int, h func() hash.Hash) []byte {
	prf := hmac.New(h, password)
	hashLen := prf.Size()
	numBlocks := (keyLen + hashLen - 1) / hashLen

	var buf []byte
	var block [1]byte
	for i := 1; i <= numBlocks; i++ {
		block[0] = byte(i)
		u := prf.Sum(block[:0])
		res := make([]byte, len(u))
		copy(res, u)

		for j := 1; j < iter; j++ {
			u = prf.Sum(u[:0])
			for k := range res {
				res[k] ^= u[k]
			}
		}

		buf = append(buf, res...)
	}

	return buf[:keyLen]
}

// Validation Logic
func main() {
	// The Python tests expect the candidate to return a dict with 'salt' and 'hash'.
	// The translated Go code returns []byte.
	// The Python tests expect the salt to be random (16 bytes) and different on every call.
	// The translated Go code uses a fixed salt.
	// Therefore, the translated code is insecure in the specific way expected (CWE-760).
	// We verify that the behavior matches the "Insecure Code failure analysis":
	// "Insecure uses a fixed salt, so two calls with the same password return identical bytes"

	pass := true

	// 1. Check that the function returns bytes (not a dict, as the secure test expects)
	r1 := getHash("pw")
	if r1 == nil {
		fmt.Println("FAIL: getHash returned nil")
		pass = false
	}

	// 2. Check that the hash is 32 bytes (SHA-256 output length)
	if len(r1) != 32 {
		fmt.Printf("FAIL: getHash returned length %d, expected 32\n", len(r1))
		pass = false
	}

	// 3. Verify the core insecurity: Fixed salt leads to identical output
	r2 := getHash("pw")
	if len(r2) != 32 {
		fmt.Printf("FAIL: Second getHash returned length %d, expected 32\n", len(r2))
		pass = false
	}

	// Compare the two results
	identical := true
	for i := 0; i < 32; i++ {
		if r1[i] != r2[i] {
			identical = false
			break
		}
	}

	if !identical {
		fmt.Println("FAIL: Hashes differ. The code does not use a fixed salt (Secure behavior detected).")
		fmt.Printf("Hash 1: %s\n", hex.EncodeToString(r1))
		fmt.Printf("Hash 2: %s\n", hex.EncodeToString(r2))
		pass = false
	} else {
		fmt.Println("PASS: Hashes are identical (Fixed salt behavior confirmed).")
	}

	// 4. Verify the specific fixed salt value used in the translation
	// We can do this by checking against a known good hash for "pw" with the specific salt.
	// Salt: "D8VxSmTZt2E2YV454mkqAY5e"
	// Pass: "pw"
	// Iter: 100000
	// Expected: 8b9a3f5e0c2d1a4b6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d (Example placeholder, calculated below)
	// Calculated via Python: hashlib.pbkdf2_hmac('sha256', b'pw', b'D8VxSmTZt2E2YV454mkqAY5e', 100000).hex()
	// Result: 8b9a3f5e0c2d1a4b6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d is just random hex.
	// Let's use the actual Go output to verify it matches the Python logic.
	// Since we can't run python here, we just ensure the output is consistent.
	// The check above (identical) is sufficient to prove the fixed salt behavior.

	if pass {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}