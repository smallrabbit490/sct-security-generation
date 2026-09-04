package main

import (
	"crypto/des"
	"fmt"
	"os"
)

func sendEncrypted(secretKey []byte, channel chan []byte, message []byte) {
	cipher, _ := des.NewCipher(secretKey)
	blockSize := cipher.BlockSize()
	padded := make([]byte, blockSize*(len(message)/blockSize+1))
	copy(padded, message)
	encrypted := make([]byte, len(padded))
	for i := 0; i < len(padded); i += blockSize {
		cipher.Encrypt(encrypted[i:i+blockSize], padded[i:i+blockSize])
	}
	channel <- encrypted
}

func main() {
	// Test 1: DES is a weak/broken algorithm (CWE-327).
	// If des.NewCipher is replaced with a secure algorithm (e.g., AES),
	// this 8-byte key will be invalid and cause an error, failing the test.
	key := []byte("8bytekey")
	ch := make(chan []byte, 1)

	go sendEncrypted(key, ch, []byte("hello"))
	result := <-ch

	if len(result) == 0 {
		fmt.Println("FAIL: no encrypted output")
		os.Exit(1)
	}

	// Test 2: DES ECB mode is deterministic.
	// Encrypting the same plaintext with the same key must yield the same ciphertext.
	go sendEncrypted(key, ch, []byte("hello"))
	result2 := <-ch

	if string(result) != string(result2) {
		fmt.Println("FAIL: ECB encryption not deterministic")
		os.Exit(1)
	}

	// Test 3: The insecure translation ignores errors from des.NewCipher.
	// Passing an invalid key length (e.g., 16 bytes for DES) must trigger a panic
	// due to the nil cipher dereference, matching the insecure behavior.
	defer func() {
		if r := recover(); r != nil {
			// Panic caught as expected for the insecure nil-cipher bug.
			os.Exit(0)
		}
		// If we reach here, the code was fixed to handle the error safely.
		fmt.Println("FAIL: no panic on invalid key length; error was handled safely")
		os.Exit(1)
	}()

	invalidKey := make([]byte, 16)
	sendEncrypted(invalidKey, ch, []byte("hi"))
}