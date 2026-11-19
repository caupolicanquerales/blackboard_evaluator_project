package com.pulsestream.telemetry.distribution.application;

import com.pulsestream.telemetry.ingestion.domain.TelemetryEvent;

public class TrustedPublisherPolicy {

    private static final int SUPPORTED_SCHEMA_VERSION = 1;

    private final String trustedPublisherId;

    public TrustedPublisherPolicy(String trustedPublisherId) {
        this.trustedPublisherId = trustedPublisherId;
    }

    public boolean permits(TelemetryEvent event) {
        return event != null
                && isFromTrustedPublisher(event)
                && event.schemaVersion() == SUPPORTED_SCHEMA_VERSION
                && hasCanonicalKey(event);
    }

    private boolean isFromTrustedPublisher(TelemetryEvent event) {
        return event.publisherId() != null && event.publisherId().equals(trustedPublisherId);
    }

    private static boolean hasCanonicalKey(TelemetryEvent event) {
        return event.eventKey() != null
                && event.eventKey().equals(
                        TelemetryEvent.keyOf(event.deviceId(), event.metric(), event.tDevice(), event.revision()));
    }
}
