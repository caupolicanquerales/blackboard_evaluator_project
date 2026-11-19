package com.pulsestream.telemetry.ingestion.application;

public record IngestSummary(int appended, int rejectedValidation, int revisions, int duplicates, boolean refused) {
}
