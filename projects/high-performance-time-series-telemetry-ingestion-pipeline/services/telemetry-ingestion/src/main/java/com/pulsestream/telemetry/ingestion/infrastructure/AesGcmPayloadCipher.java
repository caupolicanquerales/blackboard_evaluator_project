package com.pulsestream.telemetry.ingestion.infrastructure;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import javax.crypto.SecretKey;

public class AesGcmPayloadCipher {

    private static final String TRANSFORMATION = "AES/GCM/NoPadding";

    private static final int IV_LENGTH = 12;

    private static final int TAG_BITS = 128;

    private static final SecureRandom RANDOM = new SecureRandom();

    private final SecretKey key;

    public AesGcmPayloadCipher(byte[] key) {
        if (key == null || key.length != 32) {
            throw new IllegalArgumentException("AES-256 key must be 32 bytes");
        }
        this.key = new SecretKeySpec(key, "AES");
    }

    public String decrypt(String ciphertext) {
        try {
            byte[] ivAndCiphertext = Base64.getDecoder().decode(ciphertext);
            if (ivAndCiphertext.length <= IV_LENGTH) {
                throw new IllegalArgumentException("Ciphertext too short");
            }
            Cipher cipher = initCipher(Cipher.DECRYPT_MODE, new GCMParameterSpec(TAG_BITS, ivAndCiphertext, 0, IV_LENGTH));
            byte[] plain = cipher.doFinal(ivAndCiphertext, IV_LENGTH, ivAndCiphertext.length - IV_LENGTH);
            return new String(plain, StandardCharsets.UTF_8);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Payload decryption failed", e);
        }
    }

    public String encrypt(String plaintext) {
        try {
            byte[] iv = new byte[IV_LENGTH];
            RANDOM.nextBytes(iv);
            Cipher cipher = initCipher(Cipher.ENCRYPT_MODE, new GCMParameterSpec(TAG_BITS, iv));
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] ivAndCiphertext = new byte[IV_LENGTH + encrypted.length];
            System.arraycopy(iv, 0, ivAndCiphertext, 0, IV_LENGTH);
            System.arraycopy(encrypted, 0, ivAndCiphertext, IV_LENGTH, encrypted.length);
            return Base64.getEncoder().encodeToString(ivAndCiphertext);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Payload encryption failed", e);
        }
    }

    private Cipher initCipher(int mode, GCMParameterSpec spec) throws GeneralSecurityException {
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        cipher.init(mode, key, spec);
        return cipher;
    }
}
