package com.pulsestream.telemetry.ingestion.infrastructure;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import com.pulsestream.telemetry.ingestion.application.RedactionPort;

public class Sha256RedactionAdapter implements RedactionPort {

    private static final String ALGORITHM = "SHA-256";
    private static final int MASK_HEX_LENGTH = 12;

    @Override
    public String mask(String value) {
        String plainText = value == null ? "" : value;
        byte[] hash = newDigest().digest(plainText.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(hash).substring(0, MASK_HEX_LENGTH);
    }

    private static MessageDigest newDigest() {
        try {
            return MessageDigest.getInstance(ALGORITHM);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("digest unavailable");
        }
    }
}
