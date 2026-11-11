package com.pulsestream.telemetry.eventlog.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class EventLogRepositoryTest {

    private final EventLogRepository repository = mock(EventLogRepository.class);
    private final TelemetrySample sample =
            new TelemetrySample("dev-1", "temp", 1000L, 21.5, 2000L, TelemetrySample.VALID);

    @Test
    void appendRecord_returnsMonoOfBoolean() {
        when(repository.appendRecord(sample)).thenReturn(Mono.just(true));

        StepVerifier.create(repository.appendRecord(sample)).expectNext(true).verifyComplete();
    }

    @Test
    void appendRevision_returnsEmptyMonoVoid() {
        when(repository.appendRevision(sample)).thenReturn(Mono.empty());

        StepVerifier.create(repository.appendRevision(sample)).verifyComplete();
    }

    @Test
    void findByDeviceAndRange_returnsFluxOfSamples() {
        when(repository.findByDeviceAndRange("dev-1", 0L, 5000L)).thenReturn(Flux.just(sample));

        StepVerifier.create(repository.findByDeviceAndRange("dev-1", 0L, 5000L))
                .expectNext(sample)
                .verifyComplete();
    }

    @Test
    void port_exposesNoUpdateOrDeleteOperations() {
        List<String> names = Arrays.stream(EventLogRepository.class.getDeclaredMethods())
                .map(m -> m.getName().toLowerCase())
                .toList();

        assertThat(names).noneMatch(n -> n.contains("update") || n.contains("delete") || n.contains("remove"));
        assertThat(names).containsExactlyInAnyOrder("appendrecord", "appendrevision", "findbydeviceandrange");
    }
}
