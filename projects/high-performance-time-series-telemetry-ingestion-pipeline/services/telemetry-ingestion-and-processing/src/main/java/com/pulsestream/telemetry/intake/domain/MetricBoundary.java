package com.pulsestream.telemetry.intake.domain;

public record MetricBoundary(String metric, double min, double max) {

public MetricBoundary(double min, double max) {
    this(null, min, max);
}
}
