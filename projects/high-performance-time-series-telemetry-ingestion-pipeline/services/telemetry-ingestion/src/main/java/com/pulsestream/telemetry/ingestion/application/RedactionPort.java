package com.pulsestream.telemetry.ingestion.application;

public interface RedactionPort {

    String mask(String value);
}
