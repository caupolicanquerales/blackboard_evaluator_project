package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Base64;
import org.junit.jupiter.api.Test;

class AesGcmPayloadCipherTest {

    private static AesGcmPayloadCipher cipher() {
        return new AesGcmPayloadCipher(new byte[32]);
    }

    @Test
    void decrypt_afterEncrypt_returnsPlaintext() {
        AesGcmPayloadCipher c = cipher();

        assertThat(c.decrypt(c.encrypt("{\"v\":1}"))).isEqualTo("{\"v\":1}");
    }

    @Test
    void encrypt_plaintext_differsFromPlaintext() {
        assertThat(cipher().encrypt("secret-payload")).isNotEqualTo("secret-payload");
    }

    @Test
    void encrypt_samePlaintextTwice_producesDifferentCiphertexts() {
        AesGcmPayloadCipher c = cipher();

        assertThat(c.encrypt("same")).isNotEqualTo(c.encrypt("same"));
    }

    @Test
    void decrypt_tamperedCiphertext_throws() {
        AesGcmPayloadCipher c = cipher();
        byte[] raw = Base64.getDecoder().decode(c.encrypt("payload"));
        raw[raw.length - 1] ^= 0x01;
        String tampered = Base64.getEncoder().encodeToString(raw);

        assertThatThrownBy(() -> c.decrypt(tampered)).isInstanceOf(RuntimeException.class);
    }

    @Test
    void decrypt_ciphertextFromOtherKey_throws() {
        String foreign = new AesGcmPayloadCipher(new byte[] {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32}).encrypt("payload");

        assertThatThrownBy(() -> cipher().decrypt(foreign)).isInstanceOf(RuntimeException.class);
    }
}
