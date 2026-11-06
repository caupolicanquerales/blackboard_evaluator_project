package com.pulsestream.telemetry.intake.infrastructure;

import com.pulsestream.telemetry.intake.domain.MetricBoundary;
import java.util.Map;
import java.util.Objects;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import org.springframework.r2dbc.core.Parameter;

@Repository
public class R2dbcMetricBoundaryRepository {

    private final DatabaseClient databaseClient;

    public R2dbcMetricBoundaryRepository(DatabaseClient databaseClient) {
        this.databaseClient = Objects.requireNonNull(databaseClient, "databaseClient");
    }

    public Mono<MetricBoundary> findByMetric(String metric) {
        Objects.requireNonNull(metric, "metric");
        return databaseClient.sql("SELECT metric, min, max FROM telemetry.metric_boundaries WHERE metric = :metric").bind("metric", Parameter.from(metric)).fetch().all().map(R2dbcMetricBoundaryRepository::toBoundary).next();
    }

    private static MetricBoundary toBoundary(Map<String, Object> row) {
        return new MetricBoundary((String) row.get("metric"), ((Number) row.get("min")).doubleValue(), ((Number) row.get("max")).doubleValue());
    }

    public Flux<MetricBoundary> findAll() {
        return databaseClient.sql("SELECT metric, min, max FROM telemetry.metric_boundaries").fetch().all().map(R2dbcMetricBoundaryRepository::toBoundary);
    }
}
