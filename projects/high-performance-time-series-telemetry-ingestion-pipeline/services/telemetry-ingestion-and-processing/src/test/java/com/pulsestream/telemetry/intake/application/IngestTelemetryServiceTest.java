package com.pulsestream.telemetry.intake.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.SensorMetricBoundaryPolicy;
import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.intake.domain.ValidationStatus;
import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class IngestTelemetryServiceTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");

    private SensorMetricBoundaryPolicy policy;
    private BoundedEventChannel<TelemetrySampleEvent> channel;
    private IngestTelemetryService service;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        policy = mock(SensorMetricBoundaryPolicy.class);
        channel = mock(BoundedEventChannel.class);
        service = new IngestTelemetryService(policy, channel);
    }

    private static TelemetrySample validated(String metric, double value, ValidationStatus status) {
        TelemetrySample sample = mock(TelemetrySample.class);
        when(sample.deviceId()).thenReturn("dev-1");
        when(sample.metric()).thenReturn(metric);
        when(sample.value()).thenReturn(value);
        when(sample.tDevice()).thenReturn(T_DEVICE);
        when(sample.status()).thenReturn(status);
        return sample;
    }

    private static IngressPacket packetOf(TelemetrySample... samples) {
        IngressPacket packet = mock(IngressPacket.class);
        when(packet.samples()).thenReturn(List.of(samples));
        return packet;
    }

    @Test
    void ingest_validSample_publishesValidEventAndEmitsCount() {
        TelemetrySample raw = mock(TelemetrySample.class);
        when(policy.validate(raw)).thenReturn(validated("temperature", 20.5, ValidationStatus.VALID));
        when(channel.publish(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.ingest(packetOf(raw))).expectNext(1).verifyComplete();

        ArgumentCaptor<TelemetrySampleEvent> captor = ArgumentCaptor.forClass(TelemetrySampleEvent.class);
        verify(channel).publish(captor.capture());
        assertThat(captor.getValue().validationStatus()).isEqualTo(TelemetrySampleEvent.VALID);
        assertThat(captor.getValue().metric()).isEqualTo("temperature");
        assertThat(captor.getValue().value()).isEqualTo(20.5);
    }

    @Test
    void ingest_invalidSample_isTaggedAndPublishedNotDropped() {
        TelemetrySample raw = mock(TelemetrySample.class);
        when(policy.validate(raw))
                .thenReturn(validated("temperature", 999.0, ValidationStatus.VALIDATION_FAILED));
        when(channel.publish(any())).thenReturn(Mono.empty());

        StepVerifier.create(service.ingest(packetOf(raw))).expectNext(1).verifyComplete();

        ArgumentCaptor<TelemetrySampleEvent> captor = ArgumentCaptor.forClass(TelemetrySampleEvent.class);
        verify(channel).publish(captor.capture());
        assertThat(captor.getValue().validationStatus()).isEqualTo(TelemetrySampleEvent.VALIDATION_FAILED);
        assertThat(captor.getValue().isValidationFailed()).isTrue();
    }

    @Test
    void ingest_mixedSamples_publishesInPacketOrderAndCountsAll() {
        TelemetrySample rawA = mock(TelemetrySample.class);
        TelemetrySample rawB = mock(TelemetrySample.class);
        TelemetrySample rawC = mock(TelemetrySample.class);
        when(policy.validate(rawA)).thenReturn(validated("a", 1.0, ValidationStatus.VALID));
        when(policy.validate(rawB)).thenReturn(validated("b", 2.0, ValidationStatus.VALIDATION_FAILED));
        when(policy.validate(rawC)).thenReturn(validated("c", 3.0, ValidationStatus.VALID));
        List<String> published = new ArrayList<>();
        when(channel.publish(any())).thenAnswer(inv -> {
            TelemetrySampleEvent event = inv.getArgument(0);
            return Mono.fromRunnable(() -> published.add(event.metric()));
        });

        StepVerifier.create(service.ingest(packetOf(rawA, rawB, rawC))).expectNext(3).verifyComplete();

        assertThat(published).containsExactly("a", "b", "c");
    }

    @Test
    void ingest_emptyPacket_emitsZeroAndPublishesNothing() {
        StepVerifier.create(service.ingest(packetOf())).expectNext(0).verifyComplete();

        verify(channel, never()).publish(any());
    }

    @Test
    void ingest_channelOverflow_propagatesErrorToCaller() {
        TelemetrySample raw = mock(TelemetrySample.class);
        when(policy.validate(raw)).thenReturn(validated("temperature", 20.5, ValidationStatus.VALID));
        when(channel.publish(any())).thenReturn(Mono.error(new IllegalStateException("channel full")));

        StepVerifier.create(service.ingest(packetOf(raw)))
                .expectErrorMatches(e -> e instanceof IllegalStateException && e.getMessage().equals("channel full"))
                .verify();
    }

    @Test
    void ingest_channelOverflowOnFirstSample_stopsPublishingRemaining() {
        TelemetrySample rawA = mock(TelemetrySample.class);
        TelemetrySample rawB = mock(TelemetrySample.class);
        when(policy.validate(rawA)).thenReturn(validated("a", 1.0, ValidationStatus.VALID));
        when(policy.validate(rawB)).thenReturn(validated("b", 2.0, ValidationStatus.VALID));
        when(channel.publish(any())).thenReturn(Mono.error(new IllegalStateException("channel full")));

        StepVerifier.create(service.ingest(packetOf(rawA, rawB))).expectError(IllegalStateException.class).verify();

        verify(channel, org.mockito.Mockito.times(1)).publish(any());
    }
}
