package com.pulsestream.telemetry.ledger.infrastructure;

import java.time.Instant;
import java.util.UUID;
import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface TelemetryRecordR2dbcRepository {

    @Query("SELECT * FROM ledger.telemetry_records WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice ORDER BY revision DESC LIMIT 1")
    Mono<TelemetryRecordEntity> findLatestRevision(@Param("deviceId") String deviceId, @Param("metric") String metric, @Param("tDevice") Instant tDevice);

    @Query("SELECT * FROM ledger.telemetry_records WHERE device_id = :deviceId AND metric = :metric AND t_device = :tDevice ORDER BY revision")
    Flux<TelemetryRecordEntity> findRevisionChain(@Param("deviceId") String deviceId, @Param("metric") String metric, @Param("tDevice") Instant tDevice);

    @Query("SELECT * FROM ledger.telemetry_records WHERE device_id = :deviceId AND t_device >= :from AND t_device < :toExclusive ORDER BY t_device, revision")
    public Flux<TelemetryRecordEntity> findHistory(@Param("deviceId") String deviceId, @Param("from") Instant from, @Param("toExclusive") Instant toExclusive);
}
