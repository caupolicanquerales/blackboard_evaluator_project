package com.pulsestream.telemetry.intake.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.RETURNS_DEEP_STUBS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.pulsestream.telemetry.intake.domain.MetricBoundary;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

class R2dbcMetricBoundaryRepositoryTest {

    private DatabaseClient databaseClient;
    private R2dbcMetricBoundaryRepository repository;

    @BeforeEach
    void setUp() {
        databaseClient = mock(DatabaseClient.class, RETURNS_DEEP_STUBS);
        repository = new R2dbcMetricBoundaryRepository(databaseClient);
    }

    private void stubRows(Flux<Map<String, Object>> rows) {
        org.mockito.Mockito.when(databaseClient.sql(anyString()).bind(anyString(), org.mockito.ArgumentMatchers.any())
                .fetch().all()).thenReturn(rows);
        org.mockito.Mockito.when(databaseClient.sql(anyString()).fetch().all()).thenReturn(rows);
    }

    @Test
    void findAll_rowsPresent_emitsMetricBoundaries() {
        stubRows(Flux.just(Map.of("metric", "cpu", "min", 0.0, "max", 100.0)));

        Flux<MetricBoundary> result = repository.findAll();

        assertThat(result.collectList().block())
                .containsExactly(new MetricBoundary("cpu", 0.0, 100.0));
    }

    @Test
    void findByMetric_knownMetric_emitsBoundary() {
        stubRows(Flux.just(Map.of("metric", "temp", "min", -40.0, "max", 125.0)));

        Mono<MetricBoundary> result = repository.findByMetric("temp");

        assertThat(result.block()).isEqualTo(new MetricBoundary("temp", -40.0, 125.0));
    }

    @Test
    void findByMetric_unknownMetric_completesEmpty() {
        stubRows(Flux.empty());

        Mono<MetricBoundary> result = repository.findByMetric("unknown");

        assertThat(result.blockOptional()).isEmpty();
    }

    @Test
    void findAll_anyCall_readsFromMetricBoundariesTableWithSelectOnly() {
        stubRows(Flux.empty());

        repository.findAll().collectList().block();

        ArgumentCaptor<String> sql = ArgumentCaptor.forClass(String.class);
        verify(databaseClient).sql(sql.capture());
        assertThat(sql.getValue().trim().toLowerCase())
                .startsWith("select")
                .contains("telemetry.metric_boundaries")
                .doesNotContain("insert", "update", "delete");
    }
}
