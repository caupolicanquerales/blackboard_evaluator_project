package com.pulsestream.telemetry.shared.config;

import com.pulsestream.telemetry.broadcasting.application.BroadcastingService;
import com.pulsestream.telemetry.broadcasting.infrastructure.ReactorTelemetryStreamGateway;
import com.pulsestream.telemetry.intake.application.IngestTelemetryService;
import com.pulsestream.telemetry.intake.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.intake.domain.SensorMetricBoundaryPolicy;
import com.pulsestream.telemetry.ledger.application.LedgerQueryService;
import com.pulsestream.telemetry.ledger.application.RecordTelemetryService;
import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.sequencing.application.SequencingService;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetryBackfillDetectedEvent;
import com.pulsestream.telemetry.shared.events.TelemetryRevisionAppendedEvent;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryStreamPublishedEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(TelemetryProperties.class)
public class TelemetryBeansConfiguration {

    @Bean
    public BoundedEventChannel<TelemetrySampleEvent> validatedSamples(TelemetryProperties properties) {
        return new BoundedEventChannel<>("validatedSamples", properties.channels().validatedSamples());
    }

    @Bean
    public BoundedEventChannel<TelemetrySampleEvent> sequencedSamples(TelemetryProperties properties) {
        return new BoundedEventChannel<>("sequencedSamples", properties.channels().sequencedSamples());
    }

    @Bean
    public BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections(TelemetryProperties properties) {
        return new BoundedEventChannel<>("backfillDetections", properties.channels().backfillDetections());
    }

    @Bean
    public BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows(TelemetryProperties properties) {
        return new BoundedEventChannel<>("closedWindows", properties.channels().closedWindows());
    }

    @Bean
    public BoundedEventChannel<TelemetryRevisionAppendedEvent> revisionsAppended(TelemetryProperties properties) {
        return new BoundedEventChannel<>("revisionsAppended", properties.channels().revisionsAppended());
    }

    @Bean
    public BoundedEventChannel<TelemetryStreamPublishedEvent> streamPublications(TelemetryProperties properties) {
        return new BoundedEventChannel<>("streamPublications", properties.channels().streamPublications());
    }

    @Bean
    public SensorMetricBoundaryPolicy sensorMetricBoundaryPolicy(TelemetryProperties properties) {
        Map<String, SensorMetricBoundary> boundaries = new LinkedHashMap<>();
        properties.boundaries().forEach((metric, boundary) -> boundaries.put(metric, new SensorMetricBoundary(metric, boundary.min(), boundary.max())));
        return new SensorMetricBoundaryPolicy(boundaries);
    }

    @Bean
    public ReactorTelemetryStreamGateway reactorTelemetryStreamGateway(TelemetryProperties properties) {
        return new ReactorTelemetryStreamGateway(properties.channels().streamSubscriberBuffer());
    }

    @Bean
    public IngestTelemetryService ingestTelemetryService(SensorMetricBoundaryPolicy policy, @Qualifier("validatedSamples") BoundedEventChannel<TelemetrySampleEvent> validatedSamples) {
        return new IngestTelemetryService(policy, validatedSamples);
    }

    @Bean
    public SequencingService sequencingService(TelemetryProperties properties, @Qualifier("sequencedSamples") BoundedEventChannel<TelemetrySampleEvent> sequencedSamples, @Qualifier("backfillDetections") BoundedEventChannel<TelemetryBackfillDetectedEvent> backfillDetections, @Qualifier("closedWindows") BoundedEventChannel<TelemetryWindowClosedEvent> closedWindows) {
        return new SequencingService(properties.reorderWindow(), properties.reorderBufferCapacity(), properties.window().size(), properties.window().slide(), sequencedSamples, backfillDetections, closedWindows);
    }

    @Bean
    public RecordTelemetryService recordTelemetryService(TelemetryLedgerRepository repository, @Qualifier("revisionsAppended") BoundedEventChannel<TelemetryRevisionAppendedEvent> revisionsAppended) {
        return new RecordTelemetryService(repository, revisionsAppended);
    }

    @Bean
    public LedgerQueryService ledgerQueryService(TelemetryLedgerRepository repository) {
        return new LedgerQueryService(repository);
    }

    @Bean
    public BroadcastingService broadcastingService(ReactorTelemetryStreamGateway gateway, @Qualifier("streamPublications") BoundedEventChannel<TelemetryStreamPublishedEvent> streamPublications, Clock clock) {
        return new BroadcastingService(gateway, streamPublications, clock);
    }

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
