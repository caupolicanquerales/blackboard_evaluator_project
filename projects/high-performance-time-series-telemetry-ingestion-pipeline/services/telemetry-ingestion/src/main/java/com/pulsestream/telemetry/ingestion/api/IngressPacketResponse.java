package com.pulsestream.telemetry.ingestion.api;

public record IngressPacketResponse(int appended, int rejectedValidation, int revisions, int duplicates) {
}
